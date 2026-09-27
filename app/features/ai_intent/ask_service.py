"""AI ask service.

Answers a user's natural-language question about their own money.
Two Gemini calls, one repository lookup, and a deterministic branch
for greetings:

    1. Classify the question with Gemini into one of eight
       ``AskKind`` values, plus an optional counterparty reference
       and period.
    2. If the kind needs data, fetch it from ``ask_repository``.
    3. Produce the answer. Greetings use a template — no Gemini call.
       Everything else gets a second Gemini call with the fetched
       data in the prompt.

Fail-soft policy:

    This is a chat feature, not a money-movement endpoint. A user
    typed a question expecting an answer; a 502 with "AI service
    unavailable" is worse than "Sorry, I didn't quite understand
    that — here's what I can help with." So every recoverable failure
    produces a valid ``AskResponse`` rather than raising:

        * Gemini returns an unknown kind string  → ``AskKind.UNKNOWN``
        * Gemini returns malformed JSON          → ``AskKind.UNKNOWN``
        * Gemini returns a bad period            → ``"all_time"``
        * Counterparty reference doesn't match   → answer says so
        * Gemini is unreachable                  → ``AskProviderUnavailableError``
        * Firestore is down while fetching data  → propagates (502)

    The last two still raise, because a user who asked about their
    balance deserves to know the balance couldn't be read — not a
    friendly "I didn't understand." Everything the model does wrong,
    though, is recoverable, because the model is the component most
    likely to surprise us.

Data safety:

    ``_fetch_data`` returns whatever ``ask_repository`` hands back,
    which may carry raw ``Decimal`` amounts — money is ``Decimal``
    everywhere else in this codebase, and there's no reason the
    repository layer here would be the exception. ``AskResponse.data``
    is ``dict[str, Any]`` (see ``ask_schemas``), so nothing at the
    schema level catches a stray ``Decimal``. ``answer_question`` runs
    the fetched data through ``_json_safe`` before it ever reaches
    ``AskResponse`` — the one place data crosses from an internal
    fetch into the externally-facing response — rather than trusting
    every router that ever calls this service to dump in JSON mode.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import Country, ErrorCode
from app.core.exceptions import NovaBanqError
from app.features.ai_intent import ask_repository
from app.features.ai_intent.ask_prompts import (
    ANSWER_PROMPT,
    ASSISTANT_NAME,
    CAPABILITY_HINT,
    CLASSIFY_PROMPT,
    GREETING_TEMPLATE,
    UNKNOWN_FALLBACK_TEMPLATE,
)
from app.features.ai_intent.ask_schemas import (
    NO_DATA_ASK_KINDS,
    AskKind,
    AskResponse,
)
from app.features.users import service as users_service

logger = logging.getLogger(__name__)


# The periods the classifier is allowed to return. Anything else gets
# coerced to "all_time" — see ``_period_to_since`` for why the coercion
# happens rather than raising.
_VALID_PERIODS = frozenset(
    {"today", "last_week", "last_month", "last_year", "all_time"}
)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class AskProviderUnavailableError(NovaBanqError):
    """Raised when Gemini itself fails during classification or answering.

    Defined locally rather than importing
    ``ai_intent.service.IntentProviderUnavailableError`` — that class
    is named and scoped for the transfer-intent parser, a different
    feature that happens to share the same underlying provider. Ask
    and intent-parsing failing for the same underlying reason doesn't
    mean one feature should raise the other's exception; a change
    scoped to one feature's error handling shouldn't have to touch the
    other's imports, and "IntentProviderUnavailableError" surfacing
    from a question like "what's my balance?" would be a confusing
    name for whoever's debugging it.
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "The AI service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Classification model
# ---------------------------------------------------------------------------

class _GeminiClassification(BaseModel):
    """The shape Gemini fills in for the classification call.

    Two nullable fields and one fixed-vocabulary field. The kind is a
    string here (not the ``AskKind`` enum) because this model is
    filled directly by Gemini, and the SDK's structured output works
    with primitive types — the service converts the string to
    ``AskKind`` afterward, with a fallback to ``UNKNOWN`` if the
    string isn't one of the eight.
    """

    kind: str | None = None
    counterparty_tag: str | None = None
    period: str | None = None


@dataclass(frozen=True)
class _Classification:
    """The service's own classification, after validation.

    ``kind`` is guaranteed to be a valid ``AskKind`` member, and
    ``period`` is guaranteed to be one of the five valid strings.
    ``counterparty_tag`` is passed through as-is — the repository is
    what resolves it, and an unresolvable value produces a friendly
    "not found" answer rather than an error.
    """

    kind: AskKind
    counterparty_tag: str | None
    period: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def answer_question(
    *,
    sender_uid: str,
    question: str,
) -> AskResponse:
    """Answer a question about the user's money.

    Args:
        sender_uid: The authenticated caller's uid.
        question: The user's question, verbatim.

    Returns:
        An ``AskResponse`` with the classification, the answer text,
        and the structured data behind the answer (or None for kinds
        that fetch nothing).

    Raises:
        UserNotFoundError: If the caller has no profile.
        AskProviderUnavailableError: If Gemini is unreachable for the
            classification call, or for an answer that genuinely
            needed the model.
        AccountUnavailableError: On a Firestore failure reading the
            account, when the question was about the balance.
        TransactionRepositoryError: On a Firestore failure reading
            transactions, when the question was about history.
    """
    profile = users_service.get_profile(sender_uid)
    country = Country(profile["country"])
    first_name = _first_name(profile)

    classification = _classify(question=question, country=country)

    # Greeting is fully deterministic — no data fetch, no answer call.
    if classification.kind is AskKind.GREETING:
        return AskResponse(
            kind=AskKind.GREETING,
            answer=GREETING_TEMPLATE.format(
                first_name=first_name,
                assistant_name=ASSISTANT_NAME,
                capability_hint=CAPABILITY_HINT,
            ),
            data=None,
        )

    # UNKNOWN short-circuits as well. The fallback template is warmer
    # than what Gemini would produce on a question that has no data
    # behind it, and it never pays for a second model call.
    if classification.kind is AskKind.UNKNOWN:
        return AskResponse(
            kind=AskKind.UNKNOWN,
            answer=UNKNOWN_FALLBACK_TEMPLATE.format(
                first_name=first_name,
                capability_hint=CAPABILITY_HINT,
            ),
            data=None,
        )

    data = _fetch_data(
        sender_uid=sender_uid,
        classification=classification,
    )
    data = _json_safe(data)

    answer = _answer(
        question=question,
        classification=classification,
        first_name=first_name,
        data=data,
    )

    return AskResponse(
        kind=classification.kind,
        answer=answer,
        data=data,
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(*, question: str, country: Country) -> _Classification:
    """Ask Gemini what kind of question this is.

    Falls back to ``AskKind.UNKNOWN`` on any recoverable failure:
    invalid JSON from the model, a kind string that isn't one of the
    eight, or a missing kind field. An unreachable provider propagates
    as ``AskProviderUnavailableError`` — the frontend shows the user a
    "try again" rather than pretending the assistant has no idea what
    they asked.
    """
    api_key, model_name = settings.require_gemini_config()
    client = genai.Client(api_key=api_key)

    system_instruction = CLASSIFY_PROMPT.format(
        assistant_name=ASSISTANT_NAME,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=question,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=_GeminiClassification,
                temperature=0.0,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini classification call failed.")
        raise AskProviderUnavailableError() from exc

    raw_text = getattr(response, "text", None)
    if not raw_text:
        logger.warning(
            "Gemini returned no classification text; falling back to "
            "UNKNOWN."
        )
        return _Classification(
            kind=AskKind.UNKNOWN, counterparty_tag=None, period="all_time"
        )

    try:
        parsed = _GeminiClassification.model_validate_json(raw_text)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Gemini classification didn't match the schema: %s",
            raw_text,
        )
        return _Classification(
            kind=AskKind.UNKNOWN, counterparty_tag=None, period="all_time"
        )

    # Coerce the kind string to AskKind, falling back to UNKNOWN on
    # anything the model invented. This is the one place a model
    # string becomes a compiler-checked enum, so the try/except here
    # is load-bearing.
    kind: AskKind
    try:
        kind = AskKind(parsed.kind) if parsed.kind else AskKind.UNKNOWN
    except ValueError:
        logger.warning(
            "Gemini returned unknown kind %r; falling back to UNKNOWN.",
            parsed.kind,
        )
        kind = AskKind.UNKNOWN

    # Period — anything not in the valid set becomes "all_time".
    period = parsed.period if parsed.period in _VALID_PERIODS else "all_time"

    # counterparty_tag is passed through as-is (or None). The
    # repository is what decides whether it matches anything.
    return _Classification(
        kind=kind,
        counterparty_tag=parsed.counterparty_tag,
        period=period,
    )


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_data(
    *,
    sender_uid: str,
    classification: _Classification,
) -> dict[str, Any] | None:
    """Fetch whatever data the classified question needs.

    Returns None for the kinds in ``NO_DATA_ASK_KINDS`` — those are
    answered from the model's own knowledge, with no account lookup.
    For the rest, dispatches to the matching repository function.

    The returned dict is not yet sanitized for the response boundary
    — that happens once, centrally, in ``answer_question`` via
    ``_json_safe``, not here on every branch.
    """
    kind = classification.kind

    if kind in NO_DATA_ASK_KINDS:
        return None

    if kind is AskKind.BALANCE:
        return ask_repository.get_balance_context(sender_uid)

    if kind is AskKind.LAST_RECIPIENT:
        last = ask_repository.get_last_outbound(sender_uid)
        # None means the caller has never sent a transfer. Return an
        # explicit marker so the answer prompt can say so warmly
        # instead of the model inventing a recipient.
        if last is None:
            return {"has_outbound_transfers": False}
        return {"has_outbound_transfers": True, "last": last}

    if kind is AskKind.SPENDING_SUMMARY:
        since = _period_to_since(classification.period)
        return ask_repository.summarize_spending(sender_uid, since)

    if kind is AskKind.COUNTERPARTY_DETAILS:
        if not classification.counterparty_tag:
            # The classifier said COUNTERPARTY_DETAILS but didn't
            # name anyone. Nothing to look up; the answer prompt is
            # instructed to ask the user who they mean.
            return {"counterparty_lookup_failed": True}
        history = ask_repository.get_counterparty_history(
            sender_uid, classification.counterparty_tag
        )
        if history is None:
            return {"counterparty_lookup_failed": True}
        return history

    if kind is AskKind.SPENDING_ADVICE:
        return ask_repository.summarize_for_advice(sender_uid, days=30)

    # Any kind that slipped past the classifier's eight should have
    # become UNKNOWN already. If we reach here, be defensive.
    logger.error(
        "Unhandled AskKind in _fetch_data: %s. Falling through to no data.",
        kind,
    )
    return None


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------

def _answer(
    *,
    question: str,
    classification: _Classification,
    first_name: str,
    data: dict[str, Any] | None,
) -> str:
    """Generate the human-readable answer for a data-backed question.

    A second Gemini call, with the fetched data embedded in the
    prompt. The prompt is written to cite only what's in the data —
    this is where the "no invented numbers" guarantee is enforced,
    not by the code but by the prompt's rules and the fact that the
    model never sees anything else.

    The ``{data}`` placeholder is filled with a JSON dump of the
    fetched dict (or the string "none" if there was nothing to fetch,
    which happens for GENERAL_FINANCE). JSON is deliberate: the model
    is more reliable at reading structured input than at parsing
    prose tables, and a small dict serializes to a small token count.

    An unreachable provider propagates — a question about the user's
    balance deserves an error the frontend can act on, not a
    hallucinated figure.
    """
    api_key, model_name = settings.require_gemini_config()
    client = genai.Client(api_key=api_key)

    if data is None:
        data_block = "none"
    else:
        # data has already been through _json_safe by the time it
        # reaches this function, so this is a plain, boring dump —
        # default=str remains as a defensive catch-all for anything
        # unforeseen, not the mechanism relied on for Decimal/datetime
        # (that's _json_safe's job).
        data_block = json.dumps(data, default=str, ensure_ascii=False)

    system_instruction = ANSWER_PROMPT.format(
        assistant_name=ASSISTANT_NAME,
        question=question,
        kind=classification.kind.value,
        first_name=first_name,
        data=data_block,
        capability_hint=CAPABILITY_HINT,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=question,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="text/plain",
                temperature=0.4,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini answer call failed.")
        raise AskProviderUnavailableError() from exc

    answer = getattr(response, "text", None)
    if not answer:
        logger.error("Gemini returned no answer text.")
        raise AskProviderUnavailableError()

    return answer.strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """Recursively convert a value into something safe for AskResponse.data.

    ``ask_repository``'s return values may carry raw ``Decimal``
    amounts, the same way every other money-handling module in this
    codebase does. Converting each ``Decimal`` to its exact string
    representation here — the one place fetched data crosses into the
    externally-facing ``AskResponse`` — means the guarantee doesn't
    depend on every future router remembering to dump in JSON mode
    before serializing; a generic JSON encoder that reaches this data
    will find only plain, already-safe values.

    ``datetime`` is normalized to ISO 8601 for the same reason, as a
    defensive measure — the repository is expected to format
    timestamps as strings already (see ``_answer``'s docstring), so
    this branch should rarely fire in practice.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _period_to_since(period: str) -> datetime:
    """Convert a period string into a UTC "since" timestamp.

    The five periods the classifier may return, translated into a
    moment in the past:

        * ``"today"``      → start of the current UTC day
        * ``"last_week"``  → 7 days ago
        * ``"last_month"`` → 30 days ago
        * ``"last_year"``  → 365 days ago
        * ``"all_time"``   → 1970-01-01, effectively "everything"

    Uses rolling windows rather than calendar months or years. A user
    who says "last month" almost never means "the previous calendar
    month" in a payments context — they mean "the recent past, about
    a month back." Rolling windows match that intent and avoid the
    calendar-boundary confusion that a strict calendar interpretation
    would introduce mid-month.

    Unrecognized input falls back to "all_time". The caller already
    coerced anything invalid to "all_time" in ``_classify``; this
    fallback is defensive for direct calls.
    """
    now = datetime.now(timezone.utc)

    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "last_week":
        return now - timedelta(days=7)
    if period == "last_month":
        return now - timedelta(days=30)
    if period == "last_year":
        return now - timedelta(days=365)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _first_name(profile: dict[str, Any]) -> str:
    """Return the profile's first name, or a neutral fallback.

    Mirrors ``notifications.service._first_name_of`` — same fallback,
    same reasoning. A greeting that reads "Hi !" would look broken,
    so an empty first name becomes "there".
    """
    name = profile.get("first_name")
    if not isinstance(name, str) or not name.strip():
        return "there"
    return name.strip()