"""AI intent service.

Turns a user's natural-language instruction into a structured transfer
intent and the quote needed to confirm it. The heavy lifting is a
single Gemini call with a constrained response schema; everything
else here is validation and conversion.

Two public entry points:

    * ``parse_transfer_intent(...)`` — parse only. Returns the
      structured intent plus the transfer quote for the frontend to
      render a confirmation screen. Read-only. Called by
      ``/ai/parse-transfer`` and, indirectly, by
      ``/ai/ask``'s ``TRANSFER_INTENT`` branch (via
      ``confirm_execute.build_transfer_intent_response``).

    * ``execute_transfer(...)`` — execute a transfer from already-
      confirmed fields. **Does not parse natural language and does not
      call Gemini.** The frontend receives a confirmation payload from
      ``/ai/ask`` or ``/ai/parse-transfer``, collects the user's PIN,
      and sends the structured fields back here for settlement. See
      ``ai_intent.confirm_execute`` for the full confirm/execute
      contract and the reasoning behind it.

The parse flow, in order:

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

Timezone discipline:
    The conversion from local wall-clock to UTC happens here, not in
    the LLM. ``COUNTRY_TIMEZONE`` maps each country to a fixed-offset
    IANA timezone (no DST across any NovaBanq market). If Gemini
    returns an unparseable ``execute_at_local``, the service raises
    ``IntentUnparseableError`` rather than guessing — the user asked
    to defer, and we must not silently settle now. An explicit
    ``"today"``/``"tomorrow"`` prefix from Gemini is honored
    literally; only an unprefixed time falls back to "assume the
    nearest future occurrence."

Error discipline:
    Every failure in the parse path raises ``IntentUnparseableError``,
    which carries the specific reason in its message. This is a
    deliberate departure from the pattern used by ``RateUnavailable``
    and other 502 errors, where the reason is kept out of the response
    and only logged — those are internal failures the caller cannot
    act on. Here the caller *is* the user, and "please include an
    amount" is exactly the message that lets them fix their input.

Provider-resilience discipline:
    Gemini's API returns transient 5xx errors (503 UNAVAILABLE being
    the common one) during demand spikes. The service absorbs these
    with a two-model fallback chain plus exponential-ish backoff on
    each model. See ``_GEMINI_MODEL_CHAIN`` and the retry schedule
    below ``_call_gemini`` for the exact policy.

Import notes:
    * The stdlib ``time`` module is imported as ``time_module``
      because ``from datetime import time`` shadows it in the local
      namespace. Pylance correctly flags ``time.sleep(...)`` as an
      attribute error under the shadowing; renaming the module import
      avoids the collision entirely.

    * ``AiExecuteTransferResult`` is imported from
      ``execute_schemas`` — the HTTP boundary module that owns it.
      That module has no imports from ``service`` or
      ``confirm_execute``, so both can depend on it without a cycle.

    * ``execute_confirmed_transfer`` is imported *inside*
      ``execute_transfer``, not at module level. ``confirm_execute``
      imports this module (as ``ai_intent_service``) at module level
      for the parser; if we imported back at module level here, the
      two modules would need each other fully defined before either
      finished loading. The local import defers that edge to call
      time, when both modules are fully loaded.
"""

import logging
import re
import time as time_module
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types as genai_types
from google.genai.errors import ClientError, ServerError
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
    AiExecuteTransferResult,
)
from app.features.ai_intent.schemas import (
    ParseIntentResponse,
    ParsedIntent,
)
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

Time-conversion rules (apply BEFORE returning execute_at_local):
- "5pm" / "5 pm" / "5PM" / "at 5pm" / "by 5pm" -> "17:00"
- "5am" / "5 am" -> "05:00"
- "9:30pm" -> "21:30"
- "noon" -> "12:00"
- "midnight" -> "00:00"
- "17:00" / "17:00:00" -> "17:00"
- "17.00" -> "17:00"
- "tomorrow at 9am" -> "tomorrow 09:00"
- "today at 5pm" -> "today 17:00"
Always return exactly two digits for hour and two for minute, \
separated by a single colon. Never return a 12-hour time without \
converting it to 24-hour first. If you cannot determine a specific \
time, return null.

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
            or is missing a required field (recipient, amount), or the
            time string couldn't be parsed.
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

    execute_at = _parse_execute_at_strict(
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
    recipient_tag: str,
    amount_minor: int,
    confirmed_recipient_uid: str,
    idempotency_key: str,
    pin: str,
    execute_at: datetime | None = None,
) -> AiExecuteTransferResult:
    """Execute (or schedule) a transfer from already-confirmed fields.

    This function **does not parse natural language and does not call
    Gemini.** The fields arrive pre-computed from a confirmation
    payload the frontend already showed the user. That is the entire
    point: the amount and recipient that settle are the amount and
    recipient the user was shown, not a second independent parse of
    the same sentence that could drift on model version rollover,
    infra-level nondeterminism, or prompt-adjacent drift.

    See ``ai_intent.confirm_execute`` for the full confirm/execute
    contract.

    Args:
        sender_uid: The authenticated caller's uid.
        recipient_tag: The recipient tag from the confirmation payload.
        amount_minor: The amount in the sender's currency, minor
            units, from the confirmation payload.
        confirmed_recipient_uid: The recipient uid the frontend showed
            the user. Re-verified against a fresh tag resolution by
            ``execute_confirmed_transfer`` before any money moves.
        idempotency_key: Client-generated unique key for this execute
            attempt. Required. Same contract as every other
            money-moving endpoint.
        pin: The PIN collected in the frontend's confirmation modal.
            Verified before any money moves.
        execute_at: If set, the transfer is scheduled instead of
            executed immediately. Null means immediate.

    Returns:
        An ``AiExecuteTransferResult`` with either ``transfer`` (kind
        IMMEDIATE) or ``scheduled_transfer`` (kind SCHEDULED) set.

    Raises:
        RecipientChangedError: If the tag no longer resolves to
            ``confirmed_recipient_uid``.
        RecipientNotFoundError: If the tag no longer resolves to any
            user at all.
        PinInvalidError, PinLockedError: From the underlying
            transfer/schedule call.
        InsufficientBalanceError, AmountBelowMinimumError,
        CorridorUnsupportedError, SelfTransferError: From the
            underlying transfer/schedule call.
    """
    # Imported locally to break the module-load cycle. ``confirm_execute``
    # imports this module (as ``ai_intent_service``) at module level for
    # the parser, so a module-level import of ``execute_confirmed_transfer``
    # here would need ``confirm_execute`` fully defined before ``service``
    # finished loading — and ``confirm_execute`` can't finish until
    # ``service`` does. Deferring the import to call time breaks the
    # cycle; by the time any code actually calls this function, both
    # modules are fully loaded.
    from app.features.ai_intent.confirm_execute import (
        execute_confirmed_transfer,
    )

    return execute_confirmed_transfer(
        sender_uid=sender_uid,
        recipient_tag=recipient_tag,
        confirmed_recipient_uid=confirmed_recipient_uid,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
        pin=pin,
        execute_at=execute_at,
    )


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------

def _validate_and_convert_extraction(
    *,
    extraction: _GeminiExtraction,
    currency: Currency,
) -> _ValidatedExtraction:
    """Run the shared post-Gemini validation and return a narrowed model.

    Factored out so the two parse entry points can never diverge on
    what counts as a valid extraction.

    Returns a ``_ValidatedExtraction`` rather than a bare ``Decimal``
    so the required-but-still-nullable fields on ``_GeminiExtraction``
    (``recipient_tag``, ``amount_major``) are narrowed to their
    proven-non-null forms in a way Pylance can follow.

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


# ---------------------------------------------------------------------------
# Gemini call — with retry and model fallback
# ---------------------------------------------------------------------------

# Model fallback chain. If the primary model returns a transient 5xx
# (503 UNAVAILABLE is common during demand spikes on Google's side),
# we retry the primary a few times with backoff, then try a fallback
# model. Both models below were verified available for the current
# API key at the time this chain was written.
#
# Order matters: the primary is a pinned model (won't drift when
# Google updates aliases). The fallback is a rolling alias that
# Google keeps pointed at *some* working Flash model, which makes it
# a decent second choice when the pinned one is under a demand spike.
_GEMINI_MODEL_CHAIN: tuple[str, ...] = (
    "gemini-3.6-flash",
    "gemini-flash-latest",
)

# Retry schedule for transient 5xx errors, per model. The first entry
# (0.0) means "no wait before the first attempt". Total worst-case
# wait is 1 + 3 = 4 seconds per model, so at most ~8 seconds if we
# exhaust both models. That is on the edge of acceptable for a chat
# UX; the point is to absorb short demand spikes, not to hold a
# request open for a minute.
_GEMINI_RETRY_DELAYS_SECONDS: tuple[float, ...] = (0.0, 1.0, 3.0)


def _call_gemini(*, text: str, country: Country) -> _GeminiExtraction:
    """Call Gemini and return the parsed extraction.

    Tries each model in ``_GEMINI_MODEL_CHAIN`` in order. For each
    model, retries transient 5xx errors up to
    ``len(_GEMINI_RETRY_DELAYS_SECONDS) - 1`` extra times with
    backoff. Non-transient errors (4xx) abort immediately; retrying
    them just wastes time.

    Also treats an empty or schema-invalid response as a retry-worthy
    failure.

    Raises:
        IntentProviderUnavailableError: If no model in the chain
            returns a usable response.
    """
    api_key, configured_model_name = settings.require_gemini_config()

    # The configured model goes first if it isn't already in the
    # chain, so an operator who sets GEMINI_MODEL to a specific value
    # overrides the built-in chain.
    model_chain: tuple[str, ...]
    if configured_model_name in _GEMINI_MODEL_CHAIN:
        model_chain = _GEMINI_MODEL_CHAIN
    else:
        model_chain = (configured_model_name, *_GEMINI_MODEL_CHAIN)

    client = genai.Client(api_key=api_key)
    system_instruction = _SYSTEM_PROMPT.format(country=country.value)

    last_exception: Exception | None = None
    retry_delays = _GEMINI_RETRY_DELAYS_SECONDS
    last_attempt_index = len(retry_delays) - 1

    for model_name in model_chain:
        for attempt_index, delay in enumerate(retry_delays):
            is_last_attempt_for_model = attempt_index == last_attempt_index

            if delay:
                time_module.sleep(delay)

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
            except ServerError as exc:
                last_exception = exc
                logger.warning(
                    "Gemini model=%s attempt=%d/%d failed with "
                    "status=%s; will %s.",
                    model_name,
                    attempt_index + 1,
                    len(retry_delays),
                    getattr(exc, "status_code", "5xx"),
                    "advance to next model"
                    if is_last_attempt_for_model
                    else "retry",
                )
                continue
            except ClientError as exc:
                logger.exception(
                    "Gemini call failed with non-retryable client "
                    "error on model=%s (status=%s).",
                    model_name,
                    getattr(exc, "status_code", "4xx"),
                )
                raise IntentProviderUnavailableError() from exc
            except Exception as exc:  # noqa: BLE001
                last_exception = exc
                logger.warning(
                    "Gemini model=%s attempt=%d/%d raised unexpected "
                    "%s; will %s.",
                    model_name,
                    attempt_index + 1,
                    len(retry_delays),
                    type(exc).__name__,
                    "advance to next model"
                    if is_last_attempt_for_model
                    else "retry",
                )
                continue

            raw_text = getattr(response, "text", None)
            if not raw_text:
                last_exception = IntentProviderUnavailableError()
                logger.warning(
                    "Gemini model=%s attempt=%d/%d returned no text; "
                    "will %s.",
                    model_name,
                    attempt_index + 1,
                    len(retry_delays),
                    "advance to next model"
                    if is_last_attempt_for_model
                    else "retry",
                )
                continue

            try:
                return _GeminiExtraction.model_validate_json(raw_text)
            except Exception as exc:  # noqa: BLE001
                last_exception = exc
                logger.warning(
                    "Gemini model=%s attempt=%d/%d returned "
                    "unparseable JSON (%s); will %s.",
                    model_name,
                    attempt_index + 1,
                    len(retry_delays),
                    raw_text[:200],
                    "advance to next model"
                    if is_last_attempt_for_model
                    else "retry",
                )
                continue

    logger.error(
        "All Gemini models exhausted: chain=%s. Last error: %s.",
        model_chain,
        last_exception,
    )
    raise IntentProviderUnavailableError() from last_exception


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _parse_amount_decimal(raw: str) -> Decimal:
    """Convert Gemini's amount string to an exact Decimal.

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


# The parser is deliberately forgiving about the input formats
# Gemini actually returns in practice.
#
# Recognized shapes:
#   * "HH:MM" and "HH:MM:SS"       -> time(hour, minute)
#   * "HH.MM"                       -> time(hour, minute)
#   * "Hpm" / "H:MMpm" / "H pm"     -> time(hour_24, minute)
#   * "noon" / "midnight"           -> time(12, 0) / time(0, 0)

_HHMM_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
_HHMM_DOT_RE = re.compile(r"^(\d{1,2})\.(\d{2})$")
_HHMM_AMPM_RE = re.compile(
    r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$",
    re.IGNORECASE,
)
_NOON_MIDNIGHT_RE = re.compile(r"^(noon|midnight)$", re.IGNORECASE)


def _coerce_time_token(token: str) -> time | None:
    """Parse a bare time token (no day prefix) into a ``datetime.time``."""
    token = token.strip()
    if not token:
        return None

    match = _NOON_MIDNIGHT_RE.match(token)
    if match:
        word = match.group(1).lower()
        return time(12, 0) if word == "noon" else time(0, 0)

    match = _HHMM_RE.match(token)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)
        return None

    match = _HHMM_DOT_RE.match(token)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)
        return None

    match = _HHMM_AMPM_RE.match(token)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = match.group(3).lower()
        if not (1 <= hour <= 12) or not (0 <= minute <= 59):
            return None
        if meridiem == "am":
            hour_24 = 0 if hour == 12 else hour
        else:  # pm
            hour_24 = 12 if hour == 12 else hour + 12
        return time(hour_24, minute)

    return None


def _parse_execute_at_strict(
    *,
    local_str: str | None,
    country: Country,
) -> datetime | None:
    """Parse a local wall-clock string into a UTC datetime, or raise."""
    if not local_str:
        return None

    tz_name = COUNTRY_TIMEZONE.get(country)
    if tz_name is None:
        logger.warning(
            "No timezone mapping for country=%s; refusing to schedule.",
            country.value,
        )
        raise IntentUnparseableError(
            "I couldn't determine your timezone for the scheduled "
            "time. Try scheduling again or send immediately."
        )

    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)

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

    parsed_time = _coerce_time_token(token)
    if parsed_time is None:
        logger.info(
            "Could not parse execute_at_local=%r; raising "
            "IntentUnparseableError instead of silently sending now.",
            local_str,
        )
        raise IntentUnparseableError(
            "I couldn't understand the time you specified. "
            "Try something like: send 5000 to david.ng tomorrow "
            "at 09:00"
        )

    target_local = datetime.combine(
        now_local.date(), parsed_time, tzinfo=tz
    ) + timedelta(days=day_offset)

    if not explicit_day and target_local <= now_local:
        target_local += timedelta(days=1)

    return target_local.astimezone(timezone.utc)