"""AI intent HTTP endpoints.

Three endpoints:

    * ``POST /ai/parse-transfer`` — parse only. Takes a user's text,
      returns the structured intent plus the transfer quote. Read-only;
      the frontend uses this to render a confirmation screen before
      committing.

    * ``POST /ai/execute-transfer`` — parse and execute. Takes a
      user's text and their PIN, and either runs an immediate transfer
      or creates a scheduled one. Returns a discriminated union so the
      frontend knows which happened without an extra round trip.

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

The combined endpoint's request carries the PIN. It does not carry
the PIN through Gemini — the PIN is passed as a separate field on the
request and never enters the prompt or the model call. The service
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
    ExecuteTransferPayload,
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
        "`POST /transfers` or `POST /transfers/scheduled` with the "
        "fields from the response when the user confirms.\n\n"
        "The recipient is resolved here, so the confirmation screen "
        "can show the recipient's full name before the user commits — "
        "the entire point of surfacing the intent back to the user "
        "before any money moves.\n\n"
        "If `intent.execute_at` is non-null, the user asked for a "
        "scheduled transfer. The immediate-transfer flow (`POST "
        "/transfers`) ignores that field, so the frontend should "
        "route scheduled intents to the scheduled-transfer endpoint "
        "instead."
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
    summary="Parse a natural-language instruction and execute it",
    description=(
        "Parses the user's text, verifies their PIN, and executes the "
        "transfer in a single call. If the text specifies a future "
        "time, a scheduled transfer is created instead of an "
        "immediate one. Returns **201 Created** on success — a new "
        "transaction or schedule is always the result.\n\n"
        "**Response shape.** The response's `data.kind` field "
        "discriminates between the two outcomes:\n\n"
        "  - `kind: \"IMMEDIATE\"` — the transfer settled. The full "
        "    `TransferResponse` is in `data.transfer`.\n"
        "  - `kind: \"SCHEDULED\"` — a schedule was created. The full "
        "    `ScheduledTransferResponse` is in `data.scheduled_transfer`.\n\n"
        "**Optional recipient confirmation.** The request may include "
        "`confirmed_recipient_uid`. When present, the tag is "
        "re-resolved and the request is rejected if it resolves to a "
        "different uid than the one provided. This lets a cautious "
        "client do the two-step flow — call `POST /ai/parse-transfer` "
        "first, show the recipient name, then call this endpoint with "
        "the uid the user actually confirmed — while a fast-path "
        "client omits the field and accepts the tag resolution at "
        "execution time.\n\n"
        "**PIN.** The `pin` field is verified before any money moves "
        "or any schedule is written, using the same lockout policy as "
        "every other money-movement endpoint. The PIN is never sent to "
        "the language model — it's a separate request field that the "
        "service handles directly."
    ),
)
def execute_transfer(
    uid: CurrentUid,
    payload: ExecuteTransferRequest,
) -> dict[str, Any]:
    """Parse the user's text and execute (or schedule) the transfer.

    Args:
        uid: The authenticated caller's uid, injected from their
            verified Firebase ID token.
        payload: The parsed and validated request body. Contains the
            user's instruction, their 5-digit PIN, and an optional
            ``confirmed_recipient_uid`` for the two-step flow. All
            validated at the schema layer.

    Returns:
        The standard envelope whose ``data`` carries either an
        ``ImmediateTransferResult`` or a ``ScheduledTransferResult``,
        discriminated by the ``kind`` field. Response status is 201
        in both success cases.

    Raises:
        IntentUnparseableError: If the text isn't a transfer request,
            or is missing a required field.
        IntentProviderUnavailableError: If Gemini is unreachable.
        UserNotFoundError: If the caller has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        RecipientConfirmationMismatchError: If the confirmed recipient
            uid doesn't match the resolved recipient.
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
    result: ExecuteTransferPayload = service.execute_transfer(
        sender_uid=uid,
        text=payload.text,
        pin=payload.pin,
        confirmed_recipient_uid=payload.confirmed_recipient_uid,
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
        "    'explain compound interest'\n\n"
        "**Response shape.** The response's `data.kind` field is the "
        "classification of the question, one of the eight ask kinds. "
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
        fetch nothing).

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