"""AI intent service.

Turns a user's natural-language instruction into a structured transfer
intent and the quote needed to confirm it. The heavy lifting is a
single Gemini call with a constrained response schema; everything
else here is validation and conversion.

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
       frontend can show the user.
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
    7. Call ``transfers_service.quote(...)`` with the minor-unit
       amount to resolve the recipient and compute the full quote.
    8. Return a ``ParseIntentResponse`` combining the extraction, the
       quote, and the original text.

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

    amount_decimal = _parse_amount_decimal(extraction.amount_major)

    try:
        amount_minor = amount_to_minor(amount_decimal, currency)
    except ValueError as exc:
        decimal_places = len(str(CURRENCY_MINOR_UNITS[currency])) - 1
        raise IntentUnparseableError(
            f"Amount {extraction.amount_major} isn't valid for "
            f"{currency.value}. Use at most {decimal_places} decimal "
            "places."
        ) from exc

    execute_at = _parse_execute_at(
        local_str=extraction.execute_at_local,
        country=country,
    )

    quote = transfers_service.quote(
        sender_uid=sender_uid,
        recipient_tag=extraction.recipient_tag,
        send_amount_minor=amount_minor,
    )

    return ParseIntentResponse(
        intent=ParsedIntent(
            action="transfer",
            amount_major=amount_decimal,
            recipient_tag=extraction.recipient_tag,
            execute_at=execute_at,
        ),
        quote=quote,
        requested_text=text,
    )


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