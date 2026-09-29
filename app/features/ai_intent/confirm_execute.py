"""AI-driven transfer confirm/execute flow.

Two halves of one feature:

    1. ``build_transfer_intent_response`` — called by
       ``ask_service.answer_question``'s ``TRANSFER_INTENT`` branch.
       Parses a chat message like "send 5000 to david.ng" into a
       structured confirmation payload the frontend can act on.
       Either returns a help message (parse incomplete) or a full
       confirmation with the quote.

    2. ``execute_confirmed_transfer`` — called by the
       ``/ai/execute-transfer`` endpoint. Takes the already-computed
       fields from the confirmation payload and settles (or schedules)
       the transfer. Never re-parses natural language, never calls
       Gemini.

Why this module exists as a separate file from ``ai_intent.service``:

    The confirm and execute halves share a *contract* — the fields
    the confirmation hands to the frontend are the exact fields the
    frontend sends back to execute. Keeping them in one module makes
    that contract legible, and keeps the changes that carry the
    contract in one place. See ``ai_intent.service`` for the parser
    those fields come from.

Design decisions this module enforces:

    * **The execute step never re-parses natural language.** It never
      calls Gemini. The safety property "the user confirmed exactly
      what executes" depends on amount/recipient/schedule being
      carried as already-computed fields end to end. Re-parsing
      "send 1500 cedis to olanrewaju.ng" twice and trusting both
      parses to agree is not a determinism guarantee any LLM call
      actually gives you, even at temperature 0.

    * **``recipient_tag`` is re-resolved fresh at execute time** and
      compared against ``confirmed_recipient_uid``. Tags can be
      released and re-claimed by a different user between the
      confirmation and the execute call; without this check, a
      transfer could silently settle to whoever holds the tag *now*
      instead of the person the user actually saw and approved.

    * **The execute call requires a client-generated
      ``idempotency_key``**, same as every other money-moving
      endpoint in this codebase. A dropped connection and a client
      retry after the user taps "confirm" must not double-execute a
      real transfer.

On the confirmation text:

    ``build_transfer_intent_response`` returns a confirmation whose
    ``answer_text`` is a *template* the caller can use as a fallback.
    The caller (``ask_service.answer_question``) does not have to use
    it — and by default does not, because it routes the confirmation
    through the same ``_answer()`` Gemini call every other Nova reply
    goes through, so the confirmation bubble sounds like Nova rather
    than like a form letter. The template only fires when Gemini is
    unreachable, so a Gemini outage does not turn a good transfer
    into an error card.

On the help message for an incomplete parse:

    The parser raises ``IntentUnparseableError`` with a specific
    message naming the field it couldn't find. That precision is
    correct for most cases — "send to david.ng" without an amount
    really does need "please include an amount," full stop. But it
    reads wrong when the user's message clearly asked to *schedule*
    a transfer and the parse failed before the time step: the
    message ends up asking for a missing amount without ever
    acknowledging that scheduling was understood. Users read that as
    a bot that wasn't listening. ``_improve_help_message`` rewrites
    the parser's message for that specific case, keeping the parser
    as the source of truth for everything else.

Shape conventions:

    ``TransferIntentConfirmation`` is a Pydantic model (frozen),
    because it crosses the HTTP boundary — the router returns it
    inside an ``AskResponse.data``, and Pydantic handles ``Decimal``
    → string, ``datetime`` → ISO 8601, and enum coercion for us.

    ``AiExecuteTransferResult`` is defined in ``execute_schemas`` (the
    HTTP boundary module for the execute endpoint) and imported here.
    The service layer returns that boundary model directly, so the
    router can pass the service's result through with no translation
    step and Pylance sees one type, not two.

    ``TransferIntentOutcome`` is a plain dataclass because it's only
    ever consumed in-process by ``ask_service.answer_question`` —
    never serialized.

Import note:
    ``IntentUnparseableError`` is imported *inside*
    ``build_transfer_intent_response``, not at module level. This
    module imports ``ai_intent_service`` (for the parser), and
    ``service.py`` imports ``execute_confirmed_transfer`` from this
    module — a genuine cycle. Moving the
    ``IntentUnparseableError`` import into the function body means
    neither module needs the other fully initialised before its own
    module-level code can run. See ``service.py``'s module docstring
    for the complementary side of this cycle.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import (
    RecipientChangedError,
    RecipientNotFoundError,
)
from app.core.utils import format_amount
from app.features.ai_intent import service as ai_intent_service
from app.features.ai_intent.execute_schemas import (
    AiExecuteTransferResult,
)
from app.features.tags import service as tags_service
from app.features.transfers import scheduled_service
from app.features.transfers import service as transfers_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confirm step — called from ask_service.answer_question
# ---------------------------------------------------------------------------

class TransferIntentConfirmation(BaseModel):
    """The structured payload the frontend renders and later replays to
    ``execute_confirmed_transfer``.

    Every field here is already-computed data from the parse-and-quote
    step. Nothing downstream re-derives any of it from the user's
    original sentence.

    ``answer_text`` is a template the caller *may* use as a fallback.
    The default caller path routes the confirmation through Gemini so
    the bubble sounds like Nova; when Gemini is unreachable, this
    field carries the string the caller should show instead.

    Frozen — this is a read-only projection handed to the client.
    """

    model_config = ConfigDict(frozen=True)

    answer_text: str = Field(
        ...,
        description=(
            "Fallback chat bubble text — used only when the caller's "
            "Gemini answer call is unreachable. When Gemini succeeds, "
            "the caller uses Gemini's reply and this field is ignored."
        ),
    )
    recipient_tag: str = Field(
        ...,
        description="Recipient's full @tag, including country suffix.",
    )
    recipient_display_name: str = Field(
        ...,
        description="Recipient's full name, safe to display.",
    )
    recipient_uid: str = Field(
        ...,
        description=(
            "Recipient's uid. The frontend must send this back as "
            "``confirmed_recipient_uid`` on the execute call — the "
            "whole safety property of the confirm/execute split "
            "depends on it."
        ),
    )
    amount_minor: int = Field(
        ...,
        ge=1,
        description="Amount the sender is sending, in sender-currency minor units.",
    )
    sender_currency: str = Field(
        ...,
        description="Sender's currency code (e.g. 'GHS').",
    )
    fee_minor: int = Field(
        ...,
        ge=0,
        description="Fee charged by NovaBanq, in sender-currency minor units.",
    )
    total_debit_minor: int = Field(
        ...,
        ge=1,
        description="Total debited from the sender: send + fee.",
    )
    receive_amount_minor: int = Field(
        ...,
        ge=1,
        description="Amount credited to the recipient, in recipient-currency minor units.",
    )
    rate: str = Field(
        ...,
        description=(
            "Exchange rate applied, as a decimal string, at the "
            "precision the ledger stores (6 decimal places)."
        ),
    )
    execute_at: datetime | None = Field(
        None,
        description=(
            "When the transfer should execute, if the user asked "
            "for a future time. Null for immediate transfers."
        ),
    )


@dataclass(frozen=True)
class TransferIntentOutcome:
    """The result of ``build_transfer_intent_response``.

    Internal return type — only consumed by
    ``ask_service.answer_question``. Never serialized, so no Pydantic
    base needed.

    Exactly one of ``help_message`` or ``confirmation`` is set:

        * ``help_message`` — the parse was incomplete (no amount, no
          recipient, or an unparseable time). The message is
          user-facing and should be shown in the chat as-is. No
          confirmation exists; the frontend should not prompt for a
          PIN.
        * ``confirmation`` — the parse succeeded. The frontend renders
          the confirmation bubble (either Gemini's version, or the
          template on a Gemini outage) and, on user confirm, opens
          the PIN dialog and calls ``/ai/execute-transfer``.
    """

    help_message: str | None
    confirmation: TransferIntentConfirmation | None


def build_transfer_intent_response(
    *,
    sender_uid: str,
    first_name: str,
    question: str,
) -> TransferIntentOutcome:
    """Parse a transfer command and, if complete, quote it for confirmation.

    Delegates parsing to ``ai_intent_service.parse_transfer_intent`` —
    the existing transfer-intent parser — rather than re-implementing
    extraction here. That function already owns "turn this sentence
    into recipient_tag / amount / execute_at", and it already raises
    ``IntentUnparseableError`` with a specific, user-facing message on
    an incomplete parse. This function's job is only to catch that
    exception, improve the message when the user asked to schedule,
    and shape the outcome.

    Args:
        sender_uid: The authenticated caller's uid.
        first_name: The caller's first name, for the confirmation text.
        question: The user's message, verbatim.

    Returns:
        A ``TransferIntentOutcome`` with either a help message (parse
        incomplete) or a full confirmation (parse complete and quoted).

    Raises:
        IntentProviderUnavailableError: If Gemini is unreachable for
            the parse call. Not caught — a provider outage is a real
            failure, not a chat help message.
        RecipientNotFoundError: If the parsed tag resolves to no user.
        SelfTransferError: If sender and recipient are the same user.
        CorridorUnsupportedError: If the currencies have no configured
            corridor.
        AmountBelowMinimumError: If the amount is below the minimum.
        RateUnavailableError: If no trustworthy FX rate is available.
    """
    # Imported locally to break the module-load cycle: ``service.py``
    # imports ``execute_confirmed_transfer`` from this module, and if
    # we also imported ``IntentUnparseableError`` at module level, the
    # two modules would need each other fully defined before either
    # finished loading. The class is defined early in ``service.py``
    # and this function is only called after both modules have
    # completed their imports, so a function-local import is safe.
    from app.features.ai_intent.service import IntentUnparseableError

    try:
        parsed = ai_intent_service.parse_transfer_intent(
            sender_uid=sender_uid, text=question
        )
    except IntentUnparseableError as exc:
        # The parse was incomplete — missing amount, missing
        # recipient, or an unparseable time. The parser's message is
        # usually exactly right; ``_improve_help_message`` rewrites it
        # for the one case where it isn't (see that helper's
        # docstring).
        return TransferIntentOutcome(
            help_message=_improve_help_message(
                original_message=exc.message,
                user_text=question,
            ),
            confirmation=None,
        )

    # Parsed successfully. The quote was computed inside
    # parse_transfer_intent; every field we need is on it.
    quote = parsed.quote
    execute_at = parsed.intent.execute_at

    fallback_text = _render_confirmation_text(
        first_name=first_name,
        quote=quote,
        execute_at=execute_at,
    )

    return TransferIntentOutcome(
        help_message=None,
        confirmation=TransferIntentConfirmation(
            answer_text=fallback_text,
            recipient_tag=quote.recipient.tag,
            recipient_display_name=quote.recipient.display_name,
            recipient_uid=quote.recipient.uid,
            amount_minor=quote.send_amount_minor,
            sender_currency=quote.sender_currency.value,
            fee_minor=quote.fee_minor,
            total_debit_minor=quote.total_debit_minor,
            receive_amount_minor=quote.receive_amount_minor,
            rate=quote.rate,
            execute_at=execute_at,
        ),
    )


def _render_confirmation_text(
    *,
    first_name: str,
    quote,
    execute_at: datetime | None,
) -> str:
    """Compose the fallback chat bubble for a transfer confirmation.

    Used only when the caller's Gemini answer call is unreachable. On
    the normal path, ``ask_service`` routes the confirmation through
    the same ``_answer()`` call every other Nova reply uses, so the
    bubble has Nova's voice instead of this template's.
    """
    amount_display = format_amount(
        quote.send_amount_minor, quote.sender_currency
    )
    recipient_display = quote.recipient.display_name or quote.recipient.tag

    if execute_at is None:
        return (
            f"{first_name}, I'll send {amount_display} to "
            f"{recipient_display} (@{quote.recipient.tag}). "
            "Enter your PIN to confirm."
        )

    when = execute_at.strftime("%d %b %Y at %H:%M UTC")
    return (
        f"{first_name}, I'll schedule {amount_display} to "
        f"{recipient_display} (@{quote.recipient.tag}) for {when}. "
        "Enter your PIN to confirm."
    )


# Words that indicate the user wants the transfer deferred, not sent
# now. Used by ``_improve_help_message`` to recognise a schedule
# intent even when the parse failed before the execute_at step.
#
# Deliberately conservative — "later" alone could mean "a few seconds
# later," so we also match the compound forms ("send later", "pay
# later"). A user who types "later" by itself and gets the
# schedule-aware help message is no worse off than before; a user who
# types "at 5pm" and doesn't get it would be confused.
_SCHEDULE_CUES: tuple[str, ...] = (
    "schedule",
    "scheduled",
    "tomorrow",
    "next week",
    "next month",
    "at 5pm",
    "at 6pm",
    "at 7pm",
    "at 8pm",
    "at 9pm",
    "this evening",
    "tonight",
    "in an hour",
    "in a few hours",
    "in a minute",
    "in a few minutes",
    "send later",
    "pay later",
    "transfer later",
)


def _mentions_scheduling(text: str) -> bool:
    """True when the user's message hints at a deferred transfer.

    Substring match against a fixed list of schedule cues, case-
    insensitive. Covers the phrasings real users actually type;
    anything exotic falls through to the parser's own default help
    message, which is still correct — just less warm.
    """
    lowered = text.lower()
    return any(cue in lowered for cue in _SCHEDULE_CUES)


def _improve_help_message(
    *,
    original_message: str,
    user_text: str,
) -> str:
    """Rewrite a parser help message when the user asked to schedule.

    The parser's own message is precise about the single missing
    field it noticed first (usually the amount). That precision is
    right for a straight send instruction — "send 500" without a
    recipient gets "please include who you're sending to," full
    stop. But when the user said "schedule a payment," the parser's
    message can read as if it didn't register the schedule intent at
    all, and a user who hears "please include an amount" after
    asking to schedule something reads that as a bot that wasn't
    listening.

    If the user mentioned scheduling, this returns a message that
    acknowledges it and asks for both pieces a scheduled transfer
    needs: an amount and a time. Otherwise the original message
    passes through unchanged.

    The message asks for both fields rather than the specific one
    the parser happened to notice, because in the scheduled case
    the user usually needs to provide both anyway (they gave neither
    an amount nor a time, or gave one and not the other), and asking
    for both in one line avoids a two-turn back-and-forth where the
    first turn only resolves half the problem.
    """
    if not _mentions_scheduling(user_text):
        return original_message

    return (
        "Happy to schedule that — I just need to know how much to "
        "send and when. Try something like: send 5000 to david.ng "
        "tomorrow at 09:00."
    )


# ---------------------------------------------------------------------------
# Execute step — called from the /ai/execute-transfer router
# ---------------------------------------------------------------------------

def execute_confirmed_transfer(
    *,
    sender_uid: str,
    recipient_tag: str,
    confirmed_recipient_uid: str,
    amount_minor: int,
    idempotency_key: str,
    pin: str,
    execute_at: datetime | None,
) -> AiExecuteTransferResult:
    """Execute (or schedule) a transfer the user confirmed from a chat intent.

    Every argument here is already-computed data carried over from
    ``build_transfer_intent_response``'s confirmation payload. There
    is deliberately no ``text``/``question`` parameter and no call
    into the intent parser anywhere in this function — see the module
    docstring for why re-parsing at this step is a real correctness
    gap, not a style choice.

    Args:
        sender_uid: The authenticated caller's uid.
        recipient_tag: The tag from the confirmed intent.
        confirmed_recipient_uid: The uid the frontend showed the user
            as the recipient. Re-checked against a fresh resolution of
            ``recipient_tag`` before any money moves.
        amount_minor: The amount from the confirmed intent, in the
            sender's currency's minor units.
        idempotency_key: Client-generated unique key for this execute
            attempt. Required — same contract as every other transfer
            endpoint in this codebase; a retry with the same key must
            not settle twice.
        pin: The PIN collected in the frontend's confirmation modal.
            Never present in the chat text itself.
        execute_at: If set, the transfer is scheduled via
            ``scheduled_service.schedule`` instead of executed
            immediately.

    Returns:
        An ``AiExecuteTransferResult`` with either ``transfer`` (kind
        IMMEDIATE) or ``scheduled_transfer`` (kind SCHEDULED) set.

    Raises:
        RecipientChangedError: If ``recipient_tag`` no longer resolves
            to ``confirmed_recipient_uid`` — the tag changed hands
            since the user confirmed.
        RecipientNotFoundError: If ``recipient_tag`` no longer
            resolves to any user at all.
        PinInvalidError, PinLockedError: From the underlying
            transfer/schedule call.
        InsufficientBalanceError, AmountBelowMinimumError,
        CorridorUnsupportedError, SelfTransferError: From the
            underlying transfer/schedule call, unchanged.
    """
    current_uid = tags_service.resolve_uid(recipient_tag)
    if current_uid is None:
        # Re-use the transfers feature's own not-found error rather
        # than inventing a second one for the same condition.
        raise RecipientNotFoundError()
    if current_uid != confirmed_recipient_uid:
        raise RecipientChangedError()

    if execute_at is None:
        transfer = transfers_service.execute(
            sender_uid=sender_uid,
            recipient_tag=recipient_tag,
            send_amount_minor=amount_minor,
            idempotency_key=idempotency_key,
            pin=pin,
        )
        return AiExecuteTransferResult(
            kind="IMMEDIATE",
            transfer=transfer,
            scheduled_transfer=None,
        )

    scheduled = scheduled_service.schedule(
        sender_uid=sender_uid,
        recipient_tag=recipient_tag,
        amount_minor=amount_minor,
        idempotency_key=idempotency_key,
        pin=pin,
        execute_at=execute_at,
    )
    return AiExecuteTransferResult(
        kind="SCHEDULED",
        transfer=None,
        scheduled_transfer=scheduled,
    )