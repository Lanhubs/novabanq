"""AI intent service.

Turns a user's natural-language instruction into a structured transfer
intent and the quote needed to confirm it. The heavy lifting is a
single Gemini call with a constrained response schema; everything
else here is validation and conversion.

Two public entry points, both starting from the same Gemini call:

    * ``parse_transfer_intent(...)`` — parse only. Returns the
      structured intent plus the transfer quote for the frontend to
      render a confirmation screen. Read-only.

    * ``execute_transfer(...)`` — parse and execute in one shot.
      Takes the user's text and their PIN, branches on whether the
      text specified a future time, and either runs an immediate
      transfer or creates a scheduled one. Returns a discriminated
      union so the frontend knows which happened.

The flow, in order:

    1. Load the sender's profile (needed for country and currency).
    2. Call Gemini with the user's text, the response schema, and the
       sender's country in the prompt.
    3. Parse the response into a ``_GeminiExtraction`` — a small,
       string-based model that avoids the JSON Schema precision loss
       ``Decimal`` would otherwise introduce.
    4. Validate the extraction deterministically: action first, then
       recipient, then amount. Every failure raises
       ``IntentUnparseableError`` with a specific message the
       frontend can show the user. This step returns a
       ``_ValidatedExtraction`` whose ``recipient_tag`` is typed as
       ``str`` (not ``str | None``) — the narrowing is the whole
       point of the function.
    5. Convert ``amount_major`` (a string) to a ``Decimal``, guard
       against malformed or non-finite values, and pass it through
       ``amount_to_minor`` — the same shared helper the fund_user
       script uses, so there is one major-to-minor conversion in the
       codebase. NOTE: that shared helper must raise ``ValueError`` on
       an invalid amount, never ``SystemExit`` — ``SystemExit`` is a
       ``BaseException`` and would not be caught below; it belongs
       only at the CLI script's own call site, not inside shared
       logic a web request path also calls.
    6. Convert ``execute_at_local`` (a wall-clock time string) into a
       UTC ``datetime`` using ``COUNTRY_TIMEZONE`` and ``zoneinfo``.
       Gemini does not do this arithmetic — it extracts the local
       time as text, and this service does the conversion, because
       LLM timezone math is unreliable and this value schedules real
       money movement.
    7. Branch on the parsed intent:
       - ``parse_transfer_intent`` calls ``transfers_service.quote``
         and returns a ``ParseIntentResponse``.
       - ``execute_transfer`` calls either
         ``transfers_service.execute`` (immediate) or
         ``scheduled_service.schedule`` (deferred), and returns an
         ``ExecuteTransferPayload`` discriminated by ``kind``.

Timezone discipline:
    The conversion from local wall-clock to UTC happens here, not in
    the LLM. ``COUNTRY_TIMEZONE`` maps each country to a fixed-offset
    IANA timezone (no DST across any NovaBanq market). If Gemini
    returns an unparseable ``execute_at_local``, the service returns
    ``execute_at=None`` rather than guessing — the frontend then
    treats the request as immediate, and the user is told to re-enter
    the time. An explicit ``"today"``/``"tomorrow"`` prefix from
    Gemini is honored literally; only an unprefixed time falls back to
    "assume the nearest future occurrence."

Error discipline:
    Every failure in the parse path raises ``IntentUnparseableError``,
    which carries the specific reason in its message. This is a
    deliberate departure from the pattern used by ``RateUnavailable``
    and other 502 errors, where the reason is kept out of the response
    and only logged — those are internal failures the caller cannot
    act on. Here the caller *is* the user, and "please include an
    amount" is exactly the message that lets them fix their input.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import (
    COUNTRY_TIMEZONE,
    CURRENCY_MINOR_UNITS,
    Country,
    Currency,
    ErrorCode,
)
from app.core.exceptions import NovaBanqError
from app.core.utils import amount_to_minor
from app.features.ai_intent.execute_schemas import (
    ExecuteTransferPayload,
    ImmediateTransferResult,
    ScheduledTransferResult,
)
from app.features.ai_intent.schemas import (
    ParseIntentResponse,
    ParsedIntent,
)
from app.features.tags import service as tags_service
from app.features.transfers import scheduled_service
from app.features.transfers import service as transfers_service
from app.features.users import service as users_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class IntentUnparseableError(NovaBanqError):
    """Raised when the AI cannot extract a usable transfer intent.

    The message carries the *specific* reason and is safe to show the
    user — unlike the 502-class errors elsewhere in this codebase,
    where the specific reason is deliberately kept out of the response
    because the caller cannot act on it. Here the caller is the
    person who typed the text, and the whole point of the error is to
    tell them what to fix. See the module docstring for why this
    breaks from the pattern.
    """

    status_code = 422
    code = ErrorCode.VALIDATION_ERROR


class IntentProviderUnavailableError(NovaBanqError):
    """Raised when Gemini itself fails.

    Distinct from ``IntentUnparseableError`` — that's "the user's text
    wasn't a transfer request"; this is "the model provider is down."
    The frontend shows a generic retry message for this one.
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "The AI service is temporarily unavailable."


class RecipientConfirmationMismatchError(NovaBanqError):
    """Raised when a confirmed recipient uid doesn't match resolution.

    Fires only when the request includes ``confirmed_recipient_uid``
    and the tag resolves to a different uid. That means the user
    confirmed a recipient that is no longer the recipient of that
    tag — a rare event, but exactly the case the confirmation field
    exists to catch. The frontend should refresh the recipient lookup
    and ask the user to re-confirm.
    """

    status_code = 409
    code = ErrorCode.VALIDATION_ERROR
    message = "The recipient changed since you confirmed."


# ---------------------------------------------------------------------------
# Internal extraction model
# ---------------------------------------------------------------------------

class _GeminiExtraction(BaseModel):
    """The shape Gemini fills in.

    Every field is a string or nullable. ``amount_major`` is a string
    on purpose: Gemini's structured-output schema has no decimal
    primitive, and a ``NUMBER`` field would be constrained to emit
    digits that parse as a float — the exact imprecision every other
    money path in this codebase avoids. The service converts the
    string to a ``Decimal`` and guards against malformed values.

    ``execute_at_local`` is also a string — a wall-clock time like
    ``"17:00"`` or ``"tomorrow 09:00"`` — not a timezone-aware
    timestamp. Gemini extracts what the user said; the service
    converts to UTC using the sender's country. See the module
    docstring for why.
    """

    action: str | None = None
    amount_major: str | None = None
    recipient_tag: str | None = None
    execute_at_local: str | None = None


@dataclass(frozen=True)
class _ValidatedExtraction:
    """A ``_GeminiExtraction`` whose required fields are proven present.

    The whole reason this type exists is the Pylance narrowing problem
    it solves. ``_GeminiExtraction`` has ``str | None`` on every field,
    because Gemini is free to return null for any of them. Once
    ``_validate_and_convert_extraction`` has run its checks, we know
    ``recipient_tag`` is a non-empty string and ``amount_major`` is a
    valid positive ``Decimal``. This dataclass carries that knowledge
    across the function boundary in a way Pylance can see, so callers
    don't need ``# type: ignore`` or redundant assertions.

    Frozen so the narrowed values can't be mutated downstream.
    """

    recipient_tag: str
    amount_decimal: Decimal
    execute_at_local: str | None


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You extract structured transfer intents from short user messages in a \
Pan-African payments app. The user is sending money to another user's \
@tag.

Given a message, extract exactly four fields and nothing else:

- action: "transfer" if the user is asking to send money. null otherwise.
- amount_major: The numeric amount the user wants to send, as a plain \
decimal string with no currency symbol and no thousands separators. \
For "5k" or "5K", return "5000". For "500 naira", return "500". \
null if no amount is stated.
- recipient_tag: The recipient's @tag, lowercase, without the leading \
'@'. For "@David.NG", return "david.ng". null if no recipient is \
stated.
- execute_at_local: If the user specifies when to send, return the \
local wall-clock time as a 24-hour "HH:MM" string, optionally \
prefixed with "today" or "tomorrow". Examples: "17:00", \
"tomorrow 09:00". Do NOT convert to UTC and do NOT compute any \
timezone offset — the caller handles that. null if no time is stated.

The user's country is {country}. Interpret times as the user's local \
wall-clock time in that country, but do NOT do any timezone \
arithmetic yourself — return the local time exactly as the user \
implied it.

If the message is not a transfer request (a greeting, a question, \
unrelated text), return action=null and every other field null.

Do not invent values. If the user did not state an amount, return \
null for amount_major. Do not guess.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_transfer_intent(
    *,
    sender_uid: str,
    text: str,
) -> ParseIntentResponse:
    """Parse a natural-language transfer instruction into structured form.

    Args:
        sender_uid: The authenticated caller's uid.
        text: The user's raw instruction.

    Returns:
        A ``ParseIntentResponse`` carrying the extracted intent, the
        full transfer quote (recipient resolved, fee computed, rate
        applied), and the original text.

    Raises:
        IntentUnparseableError: If the text isn't a transfer request,
            or is missing a required field (recipient, amount).
        IntentProviderUnavailableError: If Gemini is unreachable.
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        AmountBelowMinimumError: If the parsed amount is below the
            platform minimum.
        CorridorUnsupportedError: If the currency pair has no corridor.
        RateUnavailableError: If no trustworthy FX rate is available.
    """
    sender_profile = users_service.get_profile(sender_uid)
    country = Country(sender_profile["country"])
    currency = Currency(sender_profile["currency"])

    extraction = _call_gemini(text=text, country=country)
    validated = _validate_and_convert_extraction(
        extraction=extraction, currency=currency
    )

    execute_at = _parse_execute_at(
        local_str=validated.execute_at_local,
        country=country,
    )

    quote = transfers_service.quote(
        sender_uid=sender_uid,
        recipient_tag=validated.recipient_tag,
        send_amount_minor=amount_to_minor(
            validated.amount_decimal, currency
        ),
    )

    return ParseIntentResponse(
        intent=ParsedIntent(
            action="transfer",
            amount_major=validated.amount_decimal,
            recipient_tag=validated.recipient_tag,
            execute_at=execute_at,
        ),
        quote=quote,
        requested_text=text,
    )


def execute_transfer(
    *,
    sender_uid: str,
    text: str,
    pin: str,
    confirmed_recipient_uid: str | None = None,
) -> ExecuteTransferPayload:
    """Parse a natural-language instruction and execute it.

    The combined endpoint: parse the text, resolve the recipient, and
    either execute an immediate transfer or create a scheduled one,
    depending on whether the user specified a future time.

    This is the endpoint the frontend calls when it wants a single
    round trip. For the two-step flow — show the user the recipient
    name first, then commit — the frontend calls
    ``/ai/parse-transfer`` first, displays the name, and then calls
    this endpoint with ``confirmed_recipient_uid`` set to the uid the
    user actually confirmed. When that field is present, the service
    re-resolves the tag and rejects the request if the resolution
    differs from the confirmed uid — closing the gap between "what
    the user saw" and "what actually executes" without a separate
    token or session.

    Args:
        sender_uid: The authenticated caller's uid.
        text: The user's raw instruction.
        pin: The PIN the user entered. Verified before any money
            moves or any schedule is written.
        confirmed_recipient_uid: Optional. When provided, the resolved
            recipient's uid must equal this value.

    Returns:
        An ``ExecuteTransferPayload`` — either an
        ``ImmediateTransferResult`` or a ``ScheduledTransferResult``,
        discriminated by the ``kind`` field.

    Raises:
        IntentUnparseableError: If the text isn't a transfer request,
            or is missing a required field (recipient, amount).
        IntentProviderUnavailableError: If Gemini is unreachable.
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        RecipientConfirmationMismatchError: If
            ``confirmed_recipient_uid`` was provided and does not
            match the resolved recipient.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the parsed amount is below the
            platform minimum.
        CorridorUnsupportedError: If the currency pair has no
            corridor.
        PinInvalidError: If the PIN does not match.
        PinLockedError: If PIN entry is currently locked.
        RateUnavailableError: If no trustworthy rate is available.
        InsufficientBalanceError: If the sender's balance cannot
            cover the total debit (immediate path only).
        ScheduledTransferRepositoryError: On a Firestore failure in
            the scheduled path.
        LedgerRepositoryError: On a Firestore failure in the
            immediate path.
    """
    sender_profile = users_service.get_profile(sender_uid)
    country = Country(sender_profile["country"])
    currency = Currency(sender_profile["currency"])

    extraction = _call_gemini(text=text, country=country)
    validated = _validate_and_convert_extraction(
        extraction=extraction, currency=currency
    )
    amount_minor = amount_to_minor(validated.amount_decimal, currency)

    # If the frontend confirmed a recipient, verify the resolution
    # before doing anything else. This is the whole point of the
    # optional field — the frontend showed the user a name, and the
    # user committed to that specific recipient. Any drift between
    # what was shown and what the tag now resolves to is rejected.
    if confirmed_recipient_uid is not None:
        resolved_uid = tags_service.resolve_uid(validated.recipient_tag)
        if resolved_uid != confirmed_recipient_uid:
            raise RecipientConfirmationMismatchError()

    execute_at = _parse_execute_at(
        local_str=validated.execute_at_local,
        country=country,
    )

    if execute_at is None:
        # Immediate transfer. Execute through the standard path,
        # which verifies the PIN and moves the money.
        transfer_result = transfers_service.execute(
            sender_uid=sender_uid,
            recipient_tag=validated.recipient_tag,
            send_amount_minor=amount_minor,
            idempotency_key=_immediate_key(),
            pin=pin,
        )
        return ImmediateTransferResult(transfer=transfer_result)

    # Scheduled transfer. The PIN is verified here, at scheduling
    # time; the scheduler will not re-verify it when the transfer
    # eventually fires.
    scheduled_result = scheduled_service.schedule(
        sender_uid=sender_uid,
        recipient_tag=validated.recipient_tag,
        amount_minor=amount_minor,
        idempotency_key=_scheduled_key(),
        pin=pin,
        execute_at=execute_at,
    )
    return ScheduledTransferResult(scheduled_transfer=scheduled_result)


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------

def _validate_and_convert_extraction(
    *,
    extraction: _GeminiExtraction,
    currency: Currency,
) -> _ValidatedExtraction:
    """Run the shared post-Gemini validation and return a narrowed model.

    Both ``parse_transfer_intent`` and ``execute_transfer`` need
    exactly this: verify the extraction has an action, a recipient,
    and an amount; convert the amount string to a Decimal; ensure it's
    valid for the currency. Factored out so the two entry points can
    never diverge on what counts as a valid extraction.

    Returns a ``_ValidatedExtraction`` rather than a bare ``Decimal``
    so the required-but-still-nullable fields on ``_GeminiExtraction``
    (``recipient_tag``, ``amount_major``) are narrowed to their
    proven-non-null forms in a way Pylance can follow. Without this,
    every caller would need a redundant ``assert x is not None`` or a
    ``# type: ignore`` after the checks — the caller would "know" the
    guarantee was made, but the type checker would not.

    Args:
        extraction: The result of ``_call_gemini``.
        currency: The sender's currency, used to bound the amount's
            decimal precision.

    Returns:
        A ``_ValidatedExtraction`` with the recipient tag as a
        non-empty ``str`` and the amount as an exact positive
        ``Decimal``.

    Raises:
        IntentUnparseableError: If the action isn't ``"transfer"``, or
            the recipient or amount is missing, or the amount isn't a
            valid Decimal or is too precise for the currency.
    """
    # Deterministic check order: action -> recipient -> amount. A
    # message that's missing both a recipient and an amount should
    # always produce the same error, so the frontend's hint is
    # reproducible.
    if extraction.action != "transfer":
        raise IntentUnparseableError(
            "I couldn't understand that as a transfer request. "
            "Try something like: send 5000 to david.ng"
        )

    if not extraction.recipient_tag:
        raise IntentUnparseableError(
            "Please include who you're sending to. "
            "Try something like: send 5000 to david.ng"
        )

    if not extraction.amount_major:
        raise IntentUnparseableError(
            "Please include an amount. "
            "Try something like: send 5000 to david.ng"
        )

    # The two checks above guarantee these are non-empty strings.
    # Binding them to locals lets Pylance narrow the type from
    # ``str | None`` to ``str`` for the rest of the function body.
    recipient_tag: str = extraction.recipient_tag
    amount_major_raw: str = extraction.amount_major

    amount_decimal = _parse_amount_decimal(amount_major_raw)

    try:
        amount_to_minor(amount_decimal, currency)
    except ValueError as exc:
        decimal_places = len(str(CURRENCY_MINOR_UNITS[currency])) - 1
        raise IntentUnparseableError(
            f"Amount {amount_major_raw} isn't valid for "
            f"{currency.value}. Use at most {decimal_places} decimal "
            "places."
        ) from exc

    return _ValidatedExtraction(
        recipient_tag=recipient_tag,
        amount_decimal=amount_decimal,
        execute_at_local=extraction.execute_at_local,
    )


def _immediate_key() -> str:
    """Fresh idempotency key for the immediate-transfer path.

    A UUIDv4 wrapped in an ``ai-`` prefix for log legibility. Each
    call gets a fresh key — two identical instructions from the same
    user at different moments are two distinct transfers, and a
    retry of a single call is protected by the client retrying with
    the same key, not by the server deriving one deterministically.
    """
    return f"ai-{uuid.uuid4().hex}"


def _scheduled_key() -> str:
    """Fresh idempotency key for the scheduled-transfer path.

    Same shape as ``_immediate_key``. The scheduled-transfer service
    derives its Firestore document id from this key via UUIDv5, so
    the key itself only needs to be unique and log-legible.
    """
    return f"ai-sched-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _call_gemini(*, text: str, country: Country) -> _GeminiExtraction:
    """Call Gemini and return the parsed extraction.

    The model is configured with a response schema derived from
    ``_GeminiExtraction``, so the response is constrained to the
    expected JSON shape. The schema fields are all strings or nulls —
    see ``_GeminiExtraction`` for why.

    Raises:
        IntentProviderUnavailableError: If Gemini is unreachable or
            returns an unparseable response.
    """
    api_key, model_name = settings.require_gemini_config()
    client = genai.Client(api_key=api_key)

    system_instruction = _SYSTEM_PROMPT.format(country=country.value)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=text,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=_GeminiExtraction,
                temperature=0.0,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — any Gemini failure
        logger.exception("Gemini call failed for intent parse.")
        raise IntentProviderUnavailableError() from exc

    raw_text = getattr(response, "text", None)
    if not raw_text:
        logger.error("Gemini returned no text for intent parse.")
        raise IntentProviderUnavailableError()

    try:
        return _GeminiExtraction.model_validate_json(raw_text)
    except Exception as exc:  # noqa: BLE001 — schema-constrained but not guaranteed
        logger.exception(
            "Gemini response didn't match the extraction schema: %s",
            raw_text,
        )
        raise IntentProviderUnavailableError() from exc


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _parse_amount_decimal(raw: str) -> Decimal:
    """Convert Gemini's amount string to an exact Decimal.

    Gemini is instructed to return a plain decimal string like
    ``"5000"`` or ``"19.99"``. The schema constrains it, but
    constraint is not a guarantee — a stray symbol or an empty string
    can still arrive. This guard converts cleanly or raises a message
    the user can act on.

    ``is_finite()`` is checked before any comparison, exactly as
    ``client.py`` and ``repository.py`` do for rates: an untrusted
    ``Decimal`` can be ``Infinity`` (which passes a bare ``<= 0``
    check silently) or ``NaN`` (whose ordering comparisons raise
    ``InvalidOperation`` outside this function's own try/except if
    left unguarded).

    Raises:
        IntentUnparseableError: If the string isn't a valid decimal,
            or is not a finite positive number.
    """
    cleaned = raw.strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise IntentUnparseableError(
            f"I couldn't read the amount {raw!r}. "
            "Try something like: send 5000 to david.ng"
        ) from exc

    if not value.is_finite() or value <= 0:
        raise IntentUnparseableError(
            f"Amount must be a positive number, got {raw!r}."
        )

    return value


def _parse_execute_at(
    *,
    local_str: str | None,
    country: Country,
) -> datetime | None:
    """Convert a local wall-clock string to a UTC datetime.

    Gemini is instructed to return the local time (e.g. ``"17:00"``
    or ``"tomorrow 09:00"``) and NOT to do any timezone math. This
    function does the conversion deterministically using the sender's
    country's IANA timezone.

    An explicit ``"today"``/``"tomorrow"`` prefix is honored as given.
    Only an unprefixed time falls back to "assume the nearest future
    occurrence" (rolling to tomorrow if that time has already passed
    today) — that heuristic must not override an explicit day the user
    stated.

    Returns ``None`` on any parse failure — the frontend then treats
    the intent as immediate, and the user is shown the current quote
    without a scheduled time. Failing open here is the right call:
    an unparseable time should not block a transfer the user might
    still want to send now.

    Args:
        local_str: The local wall-clock string from Gemini, or None.
        country: The sender's country, used to select the timezone.

    Returns:
        A timezone-aware UTC ``datetime``, or ``None`` if no time was
        given or the string could not be parsed.
    """
    if not local_str:
        return None

    tz_name = COUNTRY_TIMEZONE.get(country)
    if tz_name is None:
        logger.warning(
            "No timezone mapping for country=%s; skipping execute_at.",
            country.value,
        )
        return None

    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)

    # Normalize the input and pull off an explicit day prefix, if any.
    # The prefix is honored literally — it is not just discarded after
    # stripping, and it is not allowed to be overridden by the
    # "roll to tomorrow if already passed" fallback below.
    token = local_str.strip().lower()
    day_offset = 0
    explicit_day = False
    if token.startswith("tomorrow"):
        token = token[len("tomorrow"):].strip()
        day_offset = 1
        explicit_day = True
    elif token.startswith("today"):
        token = token[len("today"):].strip()
        day_offset = 0
        explicit_day = True

    try:
        hour_str, minute_str = token.split(":", 1)
        parsed_time = time(int(hour_str), int(minute_str))
    except (ValueError, IndexError):
        logger.info(
            "Could not parse execute_at_local=%r; treating as immediate.",
            local_str,
        )
        return None

    target_local = datetime.combine(
        now_local.date(), parsed_time, tzinfo=tz
    ) + timedelta(days=day_offset)

    # Only apply the "nearest future occurrence" fallback when Gemini
    # didn't state a day explicitly. An explicit "today 09:00" that has
    # already passed is left as-is; it is not this function's job to
    # decide whether a transfer can be scheduled in the past.
    if not explicit_day and target_local <= now_local:
        target_local += timedelta(days=1)

    return target_local.astimezone(timezone.utc)