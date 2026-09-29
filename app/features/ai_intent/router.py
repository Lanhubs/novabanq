"""AI intent HTTP endpoints.

Three endpoints:

    * ``POST /ai/parse-transfer`` — parse only. Takes a user's text,
      returns the structured intent plus the transfer quote. Read-only;
      the frontend uses this to render a confirmation screen before
      committing.

    * ``POST /ai/execute-transfer`` — execute a transfer the user has
      already confirmed. Takes the **structured fields** the frontend
      received from a prior parse/ask call, plus the user's PIN and an
      idempotency key. Does **not** re-parse natural language and does
      **not** call Gemini — see ``ai_intent.confirm_execute``'s module
      docstring for why.

    * ``POST /ai/ask`` — the financial assistant. Takes a
      plain-language question and returns an answer grounded in the
      caller's own data: balance, transaction history, spending
      summaries, counterparty details, advice, or a general money
      question answered from the model's own knowledge.

All three endpoints are authenticated via Firebase ID token, the same
as every other user-facing endpoint. The sender's uid is needed
because the amount parsed from the user's text is in their currency,
the timezone is theirs, and the data behind Nova's answers is scoped
to them.

The execute endpoint's request carries the PIN. It does not carry the
PIN through Gemini — the PIN is passed as a separate field on the
request and never enters a prompt or a model call. The service
verifies it against the sender's stored hash through the same
``users_service.verify_pin_for_uid`` path every other money-movement
endpoint uses.

The ask endpoint's request carries no PIN — it is a read-only
assistant. The caller can ask about their balance, their history, or
a money concept without authenticating anything beyond the request's
Firebase token.

Status code on ``execute-transfer``:
    Returns **201 Created**, matching this codebase's convention for
    endpoints that create a resource — ``POST /transfers``,
    ``POST /transfers/scheduled``, and ``POST /users/me`` all return
    201. The endpoint creates either a ledger transaction (immediate)
    or a scheduled-transfer document (deferred); both are new
    resources. Clients should gate on the response envelope's
    ``success`` field, not on the specific status code — the two
    success variants both return 201, and error responses carry
    whatever status their ``NovaBanqError`` subclass declares.

Serialization note:
    Responses are dumped with ``model_dump(mode="json")`` rather than
    the default ``model_dump()``. See ``app/features/transfers/router``
    for the same pattern and the reasoning: the default python mode
    leaves nested ``Decimal`` values as live objects and FastAPI's
    generic encoder downgrades them to ``float``, silently
    reintroducing the binary imprecision every money path avoids.
"""

from typing import Any

from fastapi import APIRouter

from app.core.security import CurrentUid
from app.features.ai_intent import ask_service, service
from app.features.ai_intent.ask_schemas import (
    AskRequest,
    AskResponse,
)
from app.features.ai_intent.execute_schemas import (
    AiExecuteTransferResult,
    ExecuteTransferRequest,
)
from app.features.ai_intent.schemas import (
    ParseIntentRequest,
    ParseIntentResponse,
)

router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


@router.post(
    "/ai/parse-transfer",
    response_model=dict[str, Any],
    summary="Parse a natural-language transfer instruction",
    description=(
        "Takes a user's instruction — 'send 5000 to david.ng' or "
        "'help me transfer 250 cedis to kwame.gh at 5pm' — and "
        "returns the structured intent (amount, recipient, optional "
        "scheduled time) plus the full transfer quote. The frontend "
        "renders the confirmation screen from the quote, then calls "
        "`POST /ai/execute-transfer` with the fields from the "
        "response when the user confirms.\n\n"
        "The recipient is resolved here, so the confirmation screen "
        "can show the recipient's full name before the user commits — "
        "the entire point of surfacing the intent back to the user "
        "before any money moves.\n\n"
        "If `intent.execute_at` is non-null, the user asked for a "
        "scheduled transfer. The frontend passes that field through "
        "to `/ai/execute-transfer` unchanged so the backend schedules "
        "instead of settling immediately."
    ),
)
def parse_transfer_intent(
    uid: CurrentUid,
    payload: ParseIntentRequest,
) -> dict[str, Any]:
    """Parse the user's text into a structured intent + quote."""
    result: ParseIntentResponse = service.parse_transfer_intent(
        sender_uid=uid,
        text=payload.text,
    )
    return _ok(result.model_dump(mode="json"))


@router.post(
    "/ai/execute-transfer",
    response_model=dict[str, Any],
    status_code=201,
    summary="Execute a transfer the user has already confirmed",
    description=(
        "Executes (or schedules) a transfer from the structured "
        "fields the frontend received from `/ai/ask` or "
        "`/ai/parse-transfer`. Returns **201 Created** on success — "
        "a new transaction or schedule is always the result.\n\n"
        "**No re-parsing.** The request does not carry the user's "
        "original sentence. It carries the exact fields the user was "
        "shown on the confirmation screen, so the amount and "
        "recipient that settle are the ones the user approved. The "
        "backend does not call the language model at this endpoint.\n\n"
        "**Required `confirmed_recipient_uid`.** The recipient tag "
        "is re-resolved at execute time and the request is rejected "
        "if it now points to a different user than the one provided. "
        "That's the case where a tag was released and re-claimed "
        "between the confirmation and the execute call.\n\n"
        "**Required `idempotency_key`.** Client-generated, unique per "
        "attempt. A retry after a dropped connection with the same "
        "key returns the original result without settling twice.\n\n"
        "**Response shape.** The response's `data.kind` field "
        "discriminates between the two outcomes:\n\n"
        "  - `kind: \"IMMEDIATE\"` — the transfer settled. The full "
        "    `TransferResponse` is in `data.transfer`.\n"
        "  - `kind: \"SCHEDULED\"` — a schedule was created. The full "
        "    `ScheduledTransferResponse` is in `data.scheduled_transfer`.\n\n"
        "**PIN.** The `pin` field is verified before any money moves "
        "or any schedule is written, using the same lockout policy as "
        "every other money-movement endpoint. The PIN is never sent "
        "to the language model — it's a separate request field that "
        "the service handles directly."
    ),
)
def execute_transfer(
    uid: CurrentUid,
    payload: ExecuteTransferRequest,
) -> dict[str, Any]:
    """Execute (or schedule) the transfer from confirmed fields.

    Args:
        uid: The authenticated caller's uid, injected from their
            verified Firebase ID token.
        payload: The parsed and validated request body. Contains the
            structured fields from the confirmation the user saw
            (``recipient_tag``, ``amount_minor``,
            ``confirmed_recipient_uid``, ``execute_at``), plus a
            fresh ``idempotency_key`` and the user's 5-digit ``pin``.

    Returns:
        The standard envelope whose ``data`` carries an
        ``AiExecuteTransferResult``, discriminated by the ``kind``
        field. Response status is 201 in both success cases.

    Raises:
        RecipientChangedError: If ``recipient_tag`` no longer
            resolves to ``confirmed_recipient_uid`` — the tag
            changed hands since the user confirmed.
        RecipientNotFoundError: If ``recipient_tag`` no longer
            resolves to any user at all.
        UserNotFoundError: If the caller has no profile.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the minimum.
        CorridorUnsupportedError: If the currency pair has no corridor.
        PinInvalidError: If the PIN does not match.
        PinLockedError: If PIN entry is currently locked.
        RateUnavailableError: If no trustworthy rate is available.
        InsufficientBalanceError: If the sender's balance cannot cover
            the total debit (immediate path only).
        ScheduledTransferRepositoryError: On a Firestore failure in
            the scheduled path.
        LedgerRepositoryError: On a Firestore failure in the
            immediate path.
    """
    result: AiExecuteTransferResult = service.execute_transfer(
        sender_uid=uid,
        recipient_tag=payload.recipient_tag,
        amount_minor=payload.amount_minor,
        confirmed_recipient_uid=payload.confirmed_recipient_uid,
        idempotency_key=payload.idempotency_key,
        pin=payload.pin,
        execute_at=payload.execute_at,
    )
    return _ok(result.model_dump(mode="json"))


@router.post(
    "/ai/ask",
    response_model=dict[str, Any],
    summary="Ask Nova a question about your money",
    description=(
        "The AI financial assistant. Takes a plain-language question "
        "and returns an answer grounded in the caller's own data — "
        "their balance, transaction history, spending, or a general "
        "money question.\n\n"
        "**What Nova can answer:**\n\n"
        "  - Greetings — 'hi', 'how are you', 'what can you do'\n"
        "  - Balance — 'what's my balance', 'how much do I have'\n"
        "  - Last recipient — 'who did I send money to last'\n"
        "  - Spending summaries — 'how much did I spend last month'\n"
        "  - Counterparty details — 'tell me about Chidera', 'when "
        "    did I last pay David'\n"
        "  - Spending advice — 'am I spending too much this month'\n"
        "  - General money questions — 'how can I save more', "
        "    'explain compound interest'\n"
        "  - Transfer intent — 'send 5000 to david.ng'. When the "
        "    message parses as a transfer, the response carries a "
        "    `data.action == 'confirm_transfer'` payload with the "
        "    quoted intent. The frontend should open its PIN dialog "
        "    and call `/ai/execute-transfer` with the fields from "
        "    `data.intent`.\n\n"
        "**Response shape.** The response's `data.kind` field is the "
        "classification of the question, one of the nine ask kinds. "
        "The `data.answer` field is Nova's natural-language reply, "
        "ready to display as-is. The `data.data` field carries the "
        "structured numbers behind the answer, if any were needed; "
        "it's null for greetings and general questions.\n\n"
        "**Fail-soft.** An unrecognized question becomes kind "
        "`UNKNOWN` with a helpful fallback reply, never a 500. Only "
        "a genuinely unreachable Gemini, or a Firestore failure on a "
        "data-backed kind, returns an error."
    ),
)
def ask(
    uid: CurrentUid,
    payload: AskRequest,
) -> dict[str, Any]:
    """Answer a question about the caller's money.

    Args:
        uid: The authenticated caller's uid, injected from their
            verified Firebase ID token. All data the answer is
            grounded in is scoped to this uid — Nova never sees
            another user's transactions.
        payload: The parsed and validated request body. Contains the
            caller's question, validated for length.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``AskResponse`` — the classified kind, the answer text, and
        the structured data behind the answer (or None for kinds that
        fetch nothing). For a ``TRANSFER_INTENT`` reply, ``data``
        carries an ``action`` and an ``intent`` block so the frontend
        can complete the transfer without a second parse.

    Raises:
        UserNotFoundError: If the caller has no profile.
        AskProviderUnavailableError: If Gemini is unreachable for
            classification, or for an answer that needed the model.
        AccountUnavailableError: On a Firestore failure reading the
            account, when the question was about the balance.
        TransactionRepositoryError: On a Firestore failure reading
            transactions, when the question was about history.
    """
    result: AskResponse = ask_service.answer_question(
        sender_uid=uid,
        question=payload.question,
    )
    return _ok(result.model_dump(mode="json"))