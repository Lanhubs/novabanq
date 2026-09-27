"""Transfer HTTP endpoints.

This module is the HTTP boundary for the transfers feature. It is
deliberately thin: every handler parses an authenticated request,
delegates all decision-making to ``app.features.transfers.service``
or ``app.features.transfers.scheduled_service``, and wraps the result
in the platform's standard response envelope.

Nothing in this file touches Firestore, the ledger, the FX provider,
or any business rule. If you find yourself wanting to add logic here,
it almost certainly belongs in the service layer instead.

Architecture notes that apply to every handler below:

* Handlers are ``def``, not ``async def``.
  The entire downstream stack — Firestore, the ledger, the currency
  cache, the users service — is synchronous. Declaring an ``async def``
  handler would run it on the event loop and block every other request
  while it waits on network I/O. FastAPI runs plain ``def`` handlers in
  its threadpool instead, which is exactly what this codebase needs.
  This is enforced project-wide; see the handoff document's
  architectural rules.

* Authentication is injected, never parsed.
  The ``uid: CurrentUid`` parameter resolves to a FastAPI dependency
  that verifies the caller's Firebase ID token and extracts the uid.
  A request with a missing, malformed, or expired token never reaches
  the handler body — the dependency raises before that point, and the
  global exception handler serializes it into the standard envelope
  with a 401. Handlers can therefore trust ``uid`` completely; it is
  the *only* source of caller identity. The request body is never
  trusted to state who the caller is.

* Responses are wrapped, never returned bare.
  Every successful response goes through ``_ok(...)``, producing the
  platform envelope::

      {"success": true, "data": {...}, "error": null}

  Pydantic response models are serialized with
  ``model_dump(mode="json")`` before being handed to ``_ok``, so the
  envelope's ``data`` field always contains a plain
  JSON-serializable dict — never a model instance. JSON mode matters:
  the default python mode leaves nested ``Decimal`` values as live
  objects in the returned dict, and FastAPI's generic encoder
  downgrades those to ``float``, silently reintroducing the binary
  imprecision every money path in this codebase avoids.

* Errors propagate, they are not caught.
  Every error the service can raise is a ``NovaBanqError`` subclass
  carrying its own HTTP status and machine-readable ``error.code``.
  The global handler registered in ``app.main`` catches them and
  produces the error arm of the same envelope. Catching them here
  would duplicate that logic in every router for no benefit, and would
  risk each router translating errors slightly differently. The rule
  is simple: routers do not try/except on ``NovaBanqError``.

Route ordering note:
    ``/scheduled`` and ``""`` are both flat, non-parameterized paths,
    so their registration order has no effect on FastAPI's matching —
    neither can shadow the other. The scheduled routes are grouped
    after the immediate-transfer routes for readability, not for
    correctness. If a parameterized path like ``/{transaction_id}``
    is ever added under this prefix, it must be registered *after*
    ``/scheduled`` to avoid the parameterized matcher swallowing
    ``POST /transfers/scheduled`` first.
"""

from typing import Any

from fastapi import APIRouter

from app.core.security import CurrentUid
from app.features.transfers import scheduled_service, service
from app.features.transfers.scheduled_schemas import (
    ScheduleTransferRequest,
    ScheduledTransferListResponse,
    ScheduledTransferResponse,
)
from app.features.transfers.schemas import (
    QuoteRequest,
    QuoteResponse,
    TransferRequest,
    TransferResponse,
)

# Router object for this feature. Routes declared on it are *relative*;
# the prefix ("/transfers") and the OpenAPI tag ("transfers") are applied
# when this router is mounted in ``app/api/v1/router.py``. Keeping the
# prefix out of this file means the feature can be remounted elsewhere
# (a versioned API, an internal admin surface) without editing handlers.
router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    """Wrap a successful payload in the platform's response envelope.

    Defined inline here, and in every other router, rather than imported
    from a shared module. The function is four lines; a shared import
    would couple every router to a common utility module for no real
    gain, and would obscure at each call site exactly what shape is
    being returned.

    Args:
        data: The serialized payload — always the result of calling
            ``.model_dump(mode="json")`` on a Pydantic response model,
            or a plain dict for endpoints that have no dedicated model.

    Returns:
        The envelope dict ready for FastAPI to serialize as JSON.
    """
    return {"success": True, "data": data, "error": None}


# ---------------------------------------------------------------------------
# Immediate transfers
# ---------------------------------------------------------------------------

@router.post(
    "/quote",
    response_model=dict[str, Any],
    summary="Price a transfer without moving money",
    description=(
        "Resolves the recipient tag to a NovaBanq user, fetches the live "
        "FX rate for the sender's → recipient's currency corridor, and "
        "returns the complete breakdown the sender needs to confirm: "
        "amount sent, fee charged, total debited, amount the recipient "
        "receives, and the rate applied.\n\n"
        "This endpoint is read-only. It moves no money, mutates no "
        "balance, and may be called as often as the client likes. Each "
        "call recomputes from the current rate — the response carries a "
        "short-lived ``expires_at`` after which the client should "
        "re-quote before confirming. The execute endpoint recomputes "
        "everything from scratch on its own, so a stale quote is never "
        "silently honored."
    ),
)
def quote(
    uid: CurrentUid,
    payload: QuoteRequest,
) -> dict[str, Any]:
    """Return a quote for a prospective transfer.

    Args:
        uid: The authenticated caller's uid, injected from their
            verified Firebase ID token. The sender's currency is
            derived from this uid's profile — never from the request
            body, which the client could forge.
        payload: The parsed and validated request body. By the time
            this handler runs, ``recipient_tag`` has been normalized
            (lowercased, leading '@' stripped) and ``amount_minor`` has
            been confirmed to be at or above the platform minimum.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``QuoteResponse``.

    Raises:
        UserNotFoundError: If the caller has no profile — should not
            happen for an authenticated user who completed onboarding,
            but is checked defensively.
        RecipientNotFoundError: If the tag resolves to no user.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the minimum.
        CorridorUnsupportedError: If the two currencies have no
            configured FX corridor.
        RateUnavailableError: If no trustworthy rate can be obtained
            (provider down and cache too stale).
        TagRepositoryError: If the tag lookup itself fails — surfaced
            as a 502 rather than a 404, since "we could not check" is
            not the same as "does not exist".

    Note:
        These exceptions are not caught here. They propagate to the
        global handler in ``app.main``, which serializes them into the
        error arm of the envelope with the correct HTTP status and
        error code. The list above is documentation for the reader,
        not a contract enforced by this function.
    """
    result: QuoteResponse = service.quote(
        sender_uid=uid,
        recipient_tag=payload.recipient_tag,
        send_amount_minor=payload.amount_minor,
    )
    return _ok(result.model_dump(mode="json"))


@router.post(
    "",
    response_model=dict[str, Any],
    status_code=201,
    summary="Execute a transfer",
    description=(
        "Settles a transfer through the ledger. Verifies the sender's "
        "transaction PIN, rejects retries under an already-used "
        "idempotency key, confirms the sender's balance covers the "
        "total debit, and commits the money movement atomically.\n\n"
        "**Idempotency.** The client must generate a unique "
        "``idempotency_key`` per transfer attempt and reuse it verbatim "
        "on retries. A second request bearing a key that has already "
        "settled is rejected with ``409 DUPLICATE_TRANSFER`` — the "
        "original transaction is *not* re-executed, and the client "
        "should fetch the original result rather than retry again.\n\n"
        "**PIN.** The ``pin`` field is verified against the sender's "
        "stored hash using the same lockout policy as "
        "``POST /users/me/pin/verify``. Five consecutive failures lock "
        "PIN entry for twenty minutes; locked callers receive "
        "``PIN_LOCKED`` and no PIN attempt is consumed.\n\n"
        "**Status.** A successful response always carries "
        "``status: \"SETTLED\"``. Under the ledger's single-shot commit "
        "model there is no intermediate state observable to the client: "
        "a transfer that does not settle raises an error instead of "
        "returning a partial response."
    ),
)
def execute(
    uid: CurrentUid,
    payload: TransferRequest,
) -> dict[str, Any]:
    """Execute a transfer and return the settled transaction.

    Args:
        uid: The authenticated caller's uid, injected from their
            verified Firebase ID token. Used to load the sender's
            profile, verify their PIN, and check their balance.
        payload: The parsed and validated request body. Contains the
            normalized recipient tag, the send amount in minor units,
            a client-generated idempotency key, and the sender's
            5-digit PIN. All four are validated at the schema layer
            before this handler runs — including that the PIN is
            exactly the platform's fixed length and contains only
            digits.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``TransferResponse``. The embedded ``quote`` reflects the
        amounts and rate *actually applied* — it is recomputed at
        execution time and may differ from an earlier quote response
        if the rate moved between the two calls. Clients should treat
        this embedded quote as authoritative for the receipt.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        DuplicateTransferError: If the idempotency key has already
            been used by a settled transaction. Surfaces as
            ``409 DUPLICATE_TRANSFER``.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the minimum.
        CorridorUnsupportedError: If no corridor exists for the pair.
        PinInvalidError: If the PIN does not match the stored hash. A
            failed attempt is recorded against the sender's lockout
            counter.
        PinLockedError: If PIN entry is currently locked out for the
            sender. No attempt is consumed while locked.
        RateUnavailableError: If no trustworthy rate can be obtained
            at execution time — even if a quote was successfully
            issued moments earlier.
        InsufficientBalanceError: If the sender's balance cannot cover
            ``send_amount + fee``.
        InvalidIdempotencyKeyError: If the key is malformed (wrong
            length or shape). Checked before any other work, so a
            malformed key costs nothing.
        LedgerRepositoryError: On a Firestore failure while committing
            the ledger transaction. The commit is atomic — either the
            full five-leg (or three-leg, for same-currency) movement
            is applied, or none of it is.

    Note:
        As with ``quote``, these exceptions are documented for the
        reader and are not caught here. The global exception handler
        translates them into the error envelope.
    """
    result: TransferResponse = service.execute(
        sender_uid=uid,
        recipient_tag=payload.recipient_tag,
        send_amount_minor=payload.amount_minor,
        idempotency_key=payload.idempotency_key,
        pin=payload.pin,
    )
    return _ok(result.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Scheduled transfers
# ---------------------------------------------------------------------------

@router.post(
    "/scheduled",
    response_model=dict[str, Any],
    status_code=201,
    summary="Schedule a transfer for a future time",
    description=(
        "Creates a scheduled transfer. The PIN is verified now, at "
        "scheduling time, and the transfer is written as ``PENDING``. "
        "A background scheduler fires it at ``execute_at``; when it "
        "fires, the underlying transfer executes through the same "
        "ledger path as an immediate transfer.\n\n"
        "**Idempotency.** The client must generate a unique "
        "``idempotency_key`` per scheduling attempt and reuse it "
        "verbatim on retries. A second request bearing a key that has "
        "already been used returns the original schedule without "
        "consuming another PIN attempt.\n\n"
        "**PIN.** The ``pin`` field is verified against the sender's "
        "stored hash. It is *not* re-verified when the transfer fires — "
        "the schedule itself is the authorization.\n\n"
        "**Timing.** ``execute_at`` must be in the future (enforced by "
        "the request schema). The scheduler fires the transfer within "
        "a short window after that time; transfers whose window has "
        "passed are marked ``FAILED`` with reason "
        "``SCHEDULED_TRANSFER_EXPIRED`` rather than fired late."
    ),
)
def schedule_transfer(
    uid: CurrentUid,
    payload: ScheduleTransferRequest,
) -> dict[str, Any]:
    """Create a scheduled transfer.

    Args:
        uid: The authenticated caller's uid.
        payload: The parsed and validated request body. ``recipient_tag``
            has been normalized, ``amount_minor`` confirmed above the
            platform minimum, ``pin`` confirmed to be 5 digits, and
            ``execute_at`` confirmed to be a future UTC timestamp — all
            at the schema layer.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``ScheduledTransferResponse`` with status ``PENDING``.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the minimum.
        CorridorUnsupportedError: If the currency pair has no corridor.
        PinInvalidError: If the PIN does not match the stored hash.
        PinLockedError: If PIN entry is currently locked out.
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    result: ScheduledTransferResponse = scheduled_service.schedule(
        sender_uid=uid,
        recipient_tag=payload.recipient_tag,
        amount_minor=payload.amount_minor,
        idempotency_key=payload.idempotency_key,
        pin=payload.pin,
        execute_at=payload.execute_at,
    )
    return _ok(result.model_dump(mode="json"))


@router.get(
    "/scheduled",
    response_model=dict[str, Any],
    summary="List the caller's scheduled transfers",
    description=(
        "Returns the caller's scheduled transfers, newest first. "
        "Includes past ones — filter on ``status`` client-side to show "
        "only ``PENDING`` on an 'upcoming transfers' screen."
    ),
)
def list_scheduled_transfers(
    uid: CurrentUid,
) -> dict[str, Any]:
    """Return the caller's scheduled transfers.

    Args:
        uid: The authenticated caller's uid.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``ScheduledTransferListResponse``.

    Raises:
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    result: ScheduledTransferListResponse = scheduled_service.list_for_user(
        uid=uid,
    )
    return _ok(result.model_dump(mode="json"))


@router.get(
    "/scheduled/{scheduled_transfer_id}",
    response_model=dict[str, Any],
    summary="Fetch a single scheduled transfer",
    description=(
        "Returns a single scheduled transfer the caller created. A "
        "caller who is not the owner gets a 404, same as if the id "
        "didn't exist."
    ),
)
def get_scheduled_transfer(
    uid: CurrentUid,
    scheduled_transfer_id: str,
) -> dict[str, Any]:
    """Return a single scheduled transfer owned by the caller.

    Args:
        uid: The authenticated caller's uid.
        scheduled_transfer_id: The scheduled transfer to fetch.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``ScheduledTransferResponse``.

    Raises:
        ScheduledTransferNotFoundError: If the id is unknown, or the
            caller is not its owner.
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    result: ScheduledTransferResponse = scheduled_service.get_one(
        uid=uid,
        scheduled_transfer_id=scheduled_transfer_id,
    )
    return _ok(result.model_dump(mode="json"))


@router.post(
    "/scheduled/{scheduled_transfer_id}/cancel",
    response_model=dict[str, Any],
    summary="Cancel a pending scheduled transfer",
    description=(
        "Cancels a scheduled transfer that has not yet fired. Only "
        "``PENDING`` transfers can be cancelled — attempting to cancel "
        "one that has already settled, failed, or been cancelled "
        "returns a 409.\n\n"
        "If the scheduler fires the transfer at the same moment the "
        "user cancels, whichever operation reaches the Firestore "
        "transaction first wins. The loser sees a deterministic "
        "outcome: either the cancel succeeds and the fire is recorded "
        "as an anomaly, or the fire succeeds and the cancel returns "
        "409."
    ),
)
def cancel_scheduled_transfer(
    uid: CurrentUid,
    scheduled_transfer_id: str,
) -> dict[str, Any]:
    """Cancel a pending scheduled transfer.

    Args:
        uid: The authenticated caller's uid.
        scheduled_transfer_id: The scheduled transfer to cancel.

    Returns:
        The standard envelope whose ``data`` is a serialized
        ``ScheduledTransferResponse`` with status ``CANCELLED``.

    Raises:
        ScheduledTransferNotFoundError: If the id is unknown, or the
            caller is not its owner.
        ScheduledTransferStateError: If the transfer is no longer
            PENDING. Surfaces as a 409.
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    result: ScheduledTransferResponse = scheduled_service.cancel(
        uid=uid,
        scheduled_transfer_id=scheduled_transfer_id,
    )
    return _ok(result.model_dump(mode="json"))