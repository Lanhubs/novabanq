"""Scheduled-transfer service.

Orchestrates the scheduled-transfer flow: creating a schedule,
listing the caller's schedules, and executing one that's come due.

Public functions:

    * ``schedule(...)`` — verify the PIN, validate the recipient and
      amount, and write a ``PENDING`` scheduled-transfer document.
      Called by the router on ``POST /transfers/scheduled``.
    * ``list_for_user(...)`` — return the caller's scheduled transfers
      for the "upcoming transfers" screen.
    * ``get_one(...)`` — return a single scheduled transfer owned by
      the caller.
    * ``cancel(...)`` — cancel a still-``PENDING`` scheduled transfer.
    * ``execute_due(...)`` — find every PENDING scheduled transfer
      whose ``execute_at`` has passed, fire the underlying transfer
      for each, and transition the document to SETTLED or FAILED.
      Called by the scheduler loop in ``scripts/run_scheduler.py``.

The PIN is verified at *scheduling* time, when the user is present to
be challenged. It is NOT re-verified when the transfer actually
fires — the scheduler calls
``transfers_service.execute_pre_authorized``, which skips the PIN
check by contract. See that function's docstring for the security
argument.

Fire-window discipline:
    A scheduled transfer is only fired if its ``execute_at`` is within
    the last ``SCHEDULED_TRANSFER_FIRE_WINDOW_MINUTES`` minutes. A
    transfer whose window has already passed — because the scheduler
    was down, or the process restarted, or an operator paused the
    loop — is marked ``FAILED`` with reason
    ``SCHEDULED_TRANSFER_EXPIRED`` rather than fired silently hours
    late. This protects users from a burst of stale transfers
    executing all at once after an outage, surprising them with
    debits they no longer expect.

Scheduler concurrency:
    ``execute_due`` is written to be safe against *multiple* scheduler
    processes running concurrently, not just against a user cancelling
    mid-execution. Both hazards are handled by the same mechanism: the
    repository's transactional status transitions (see
    ``scheduled_repository._transition``) reject a write whose expected
    status no longer matches the document's current status. Two
    schedulers both picking up the same due transfer will each call
    ``execute_pre_authorized`` with the same deterministic idempotency
    key (the ledger deduplicates the second call) and then race to
    ``mark_settled`` — one wins, the other sees a
    ``ScheduledTransferStateError`` and logs the anomaly. The same
    error also fires if a user cancels while the scheduler is
    executing. The log messages below name both possible causes rather
    than assuming a cancel.

Interrupted-pass recovery:
    ``_fire_one`` also recovers from the case where a *previous*
    scheduler pass moved the money but was interrupted (or killed)
    between the ledger commit and ``mark_settled``. On the next pass,
    ``execute_pre_authorized`` finds the committed transaction under
    the same deterministic idempotency key and raises
    ``DuplicateTransferError``; ``_fire_one`` catches that specific
    error, looks up the transaction id, and marks the scheduled
    transfer SETTLED — closing the gap rather than recording a false
    FAILED.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.constants import (
    SCHEDULED_TRANSFER_FIRE_WINDOW_MINUTES,
    Currency,
    ErrorCode,
    ScheduledTransferStatus,
)
from app.core.exceptions import NovaBanqError
from app.features.notifications import service as notifications_service
from app.features.tags import service as tags_service
from app.features.transfers import (
    scheduled_repository,
    service as transfers_service,
    validator,
)
from app.features.transfers.scheduled_repository import (
    ScheduledTransferStateError,
)
from app.features.transfers.scheduled_schemas import (
    ScheduledTransferListResponse,
    ScheduledTransferResponse,
)
from app.features.transfers.service import DuplicateTransferError
from app.features.users import service as users_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class ScheduledTransferNotFoundError(NovaBanqError):
    """Raised when a scheduled-transfer id doesn't resolve to a document.

    Used by ``get_one`` and ``cancel`` when the id is unknown.
    """

    status_code = 404
    code = ErrorCode.SCHEDULED_TRANSFER_NOT_FOUND
    message = "No scheduled transfer found with that id."


class ScheduledTransferAccessDeniedError(NovaBanqError):
    """Raised when a caller asks about a scheduled transfer they don't own.

    Uses the same 404 code and status as ``ScheduledTransferNotFoundError``
    on purpose — the caller cannot distinguish "doesn't exist" from
    "belongs to someone else." Same reasoning as
    ``TransactionAccessDeniedError``.
    """

    status_code = 404
    code = ErrorCode.SCHEDULED_TRANSFER_NOT_FOUND
    message = "No scheduled transfer found with that id."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def schedule(
    *,
    sender_uid: str,
    recipient_tag: str,
    amount_minor: int,
    idempotency_key: str,
    pin: str,
    execute_at: datetime,
) -> ScheduledTransferResponse:
    """Create a scheduled transfer.

    Idempotent: deriving the document id from the client's idempotency
    key means a retry with the same key returns the original schedule
    without creating a second one, and without consuming another PIN
    attempt.

    The future-timestamp invariant on ``execute_at`` is enforced by the
    request schema (``ScheduleTransferRequest._validate_future``), not
    here — the schema rejects a past or timezone-naive timestamp before
    this function is ever called. This function assumes a validated
    timestamp and does not re-check it.

    Args:
        sender_uid: The authenticated caller's uid.
        recipient_tag: Normalized recipient tag.
        amount_minor: Amount in the sender's currency, minor units.
        idempotency_key: Client-generated key for deduplication.
        pin: The PIN the sender entered on the confirm screen. Verified
            here; the scheduler will not re-verify it.
        execute_at: When the transfer should run, UTC-aware. Guaranteed
            in the future by the request schema.

    Returns:
        A ``ScheduledTransferResponse`` describing the created (or
        already-existing) schedule.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        TagRepositoryError: If the tag lookup itself fails — surfaced
            as a 502 rather than a 404, since "we could not check" is
            not the same as "does not exist".
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        CorridorUnsupportedError: If the currencies have no configured
            corridor.
        PinInvalidError: If the PIN does not match.
        PinLockedError: If the PIN is currently locked.
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    sender_profile = users_service.get_profile(sender_uid)

    # Pre-flight: resolve the recipient and run the same cheap
    # validators the immediate-transfer path runs. This gives the
    # caller a synchronous error for a bad tag or a below-minimum
    # amount, rather than discovering it hours later when the
    # scheduler fires and the transfer fails.
    recipient_profile = transfers_service._resolve_recipient(recipient_tag)  # noqa: SLF001
    validator.validate_quote(
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        send_amount_minor=amount_minor,
        recipient_tag=recipient_tag,
    )

    # Derive a stable document id from the client's idempotency key.
    # Two concurrent requests with the same key produce the same id,
    # so the repository's get-or-create commits one and returns the
    # other unchanged.
    scheduled_transfer_id = _scheduled_transfer_id_from_key(idempotency_key)

    existing = scheduled_repository.get_by_id(scheduled_transfer_id)
    if existing is not None:
        # A retry. Return the existing schedule without consuming a
        # PIN attempt — the user already authorized this. Reuse the
        # recipient profile we just loaded rather than re-fetching it.
        return _response_from_doc(
            existing,
            recipient_display_name=transfers_service._display_name(recipient_profile),  # noqa: SLF001
        )

    # Verify the PIN now, at scheduling time. A lockout fires the
    # security notification, matching the immediate-transfer path.
    try:
        users_service.verify_pin_for_uid(sender_uid, pin)
    except users_service.PinLockedError:
        notifications_service.send_pin_lockout(profile=sender_profile)
        raise

    currency = Currency(sender_profile["currency"])

    doc, created = scheduled_repository.create_if_absent(
        scheduled_transfer_id,
        uid=sender_uid,
        recipient_tag=recipient_tag,
        amount_minor=amount_minor,
        sender_currency=currency,
        execute_at=execute_at,
    )

    if not created:
        # Raced with a concurrent identical request. The other one
        # won; return its document. No second PIN attempt was
        # consumed, because the loser's verify_pin_for_uid ran before
        # the race — which is fine, PIN verification is idempotent
        # when the PIN is correct.
        logger.info(
            "Scheduled transfer id=%s already existed; returning the "
            "stored record.",
            scheduled_transfer_id,
        )

    return _response_from_doc(
        doc,
        recipient_display_name=transfers_service._display_name(recipient_profile),  # noqa: SLF001
    )


def list_for_user(
    *,
    uid: str,
    limit: int = 50,
) -> ScheduledTransferListResponse:
    """Return the caller's scheduled transfers, newest first.

    Each item's recipient display name is resolved against the current
    user profile, so if the recipient has since been deleted the field
    is None rather than a stale name.

    Args:
        uid: The authenticated caller's uid.
        limit: Maximum number of items to return.

    Returns:
        A ``ScheduledTransferListResponse``.

    Raises:
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    docs = scheduled_repository.list_for_user(uid, limit=limit)
    items = [_response_from_doc(doc, resolve_recipient_name=True) for doc in docs]
    return ScheduledTransferListResponse(items=items)


def get_one(
    *,
    uid: str,
    scheduled_transfer_id: str,
) -> ScheduledTransferResponse:
    """Return a single scheduled transfer owned by the caller.

    Scoped: a caller who does not own the scheduled transfer gets the
    same 404 as if the id didn't exist. That prevents the endpoint
    from being used to enumerate other users' scheduled transfer ids.

    Args:
        uid: The authenticated caller's uid.
        scheduled_transfer_id: The scheduled transfer to fetch.

    Returns:
        A ``ScheduledTransferResponse``.

    Raises:
        ScheduledTransferNotFoundError: If the id is unknown.
        ScheduledTransferAccessDeniedError: If the id exists but the
            caller is not its owner. Same status code and error code
            as NotFound on purpose, so the caller cannot distinguish
            the two cases.
    """
    doc = scheduled_repository.get_by_id(scheduled_transfer_id)
    if doc is None:
        raise ScheduledTransferNotFoundError()
    if doc.get("uid") != uid:
        raise ScheduledTransferAccessDeniedError()
    return _response_from_doc(doc, resolve_recipient_name=True)


def cancel(
    *,
    uid: str,
    scheduled_transfer_id: str,
) -> ScheduledTransferResponse:
    """Cancel a still-``PENDING`` scheduled transfer.

    Only a ``PENDING`` transfer can be cancelled. Attempting to cancel
    one that has already settled, failed, or been cancelled raises
    ``ScheduledTransferStateError`` (from the repository's
    transactional precondition check), which this function translates
    into the existing 409 ``VALIDATION_ERROR`` response shape the
    frontend already handles for other "already finalised" states.

    Args:
        uid: The authenticated caller's uid.
        scheduled_transfer_id: The scheduled transfer to cancel.

    Returns:
        The updated ``ScheduledTransferResponse`` with status
        ``CANCELLED``.

    Raises:
        ScheduledTransferNotFoundError: If the id is unknown.
        ScheduledTransferAccessDeniedError: If the id exists but the
            caller is not its owner. Same status code and error code
            as NotFound on purpose.
        ScheduledTransferStateError: If the transfer is no longer
            PENDING — the scheduler fired it, or another caller
            already cancelled. Surfaces to the client as a 409.
        ScheduledTransferRepositoryError: On a Firestore failure.
    """
    doc = scheduled_repository.get_by_id(scheduled_transfer_id)
    if doc is None:
        raise ScheduledTransferNotFoundError()
    if doc.get("uid") != uid:
        raise ScheduledTransferAccessDeniedError()

    scheduled_repository.mark_cancelled(scheduled_transfer_id)

    # Re-read to return the current state. The state could have
    # changed again between the mark and this read only if another
    # caller raced us — but the mark itself only succeeds from
    # PENDING, so the state we observed on the read-back is a valid
    # post-transition state.
    updated = scheduled_repository.get_by_id(scheduled_transfer_id)
    if updated is None:
        # Extremely defensive: the document cannot disappear between
        # the mark and the read in normal operation.
        raise ScheduledTransferNotFoundError()
    return _response_from_doc(updated, resolve_recipient_name=True)


def execute_due(
    *,
    now: datetime | None = None,
    batch_size: int,
) -> int:
    """Fire every scheduled transfer whose time has come.

    Called by the scheduler loop. Fetches a batch of due transfers,
    runs each through ``transfers_service.execute_pre_authorized``,
    and updates its document to SETTLED or FAILED.

    Two failure categories, handled differently:

        * Business rejections (``NovaBanqError`` subclasses with
          ``status_code < 500``) are permanent for this particular
          attempt — insufficient balance, recipient deleted, corridor
          removed, and so on. The transfer is marked FAILED with the
          error code as ``failure_reason``.
        * Infrastructure failures (``status_code >= 500``) are
          transient. The transfer is left PENDING and the exception
          propagates, ending this scheduler pass. The next pass
          retries. This is deliberate: a Firestore outage or a
          provider hiccup must not permanently fail every due
          transfer for the duration of the outage.

    A failure inside one transfer does not abort the rest of the
    batch — the loop continues to the next. Only a Firestore outage
    while *listing* due transfers, or an infrastructure failure while
    *firing* one, ends the pass early.

    Args:
        now: The current time, UTC-aware. Defaults to ``datetime.now``
            in UTC; injectable for tests.
        batch_size: Maximum number of due transfers to process in this
            pass.

    Returns:
        The number of transfers processed (settled or failed). Zero if
        nothing was due.

    Raises:
        ScheduledTransferRepositoryError: On a Firestore failure while
            listing due transfers.
        NovaBanqError: Any infrastructure failure (``status_code >=
            500``) raised by the transfer service while firing a due
            transfer. Propagates so the next scheduler pass retries.
    """
    now = now or datetime.now(timezone.utc)
    window = timedelta(minutes=SCHEDULED_TRANSFER_FIRE_WINDOW_MINUTES)

    due = scheduled_repository.list_due(now=now, limit=batch_size)
    if not due:
        return 0

    processed = 0
    for doc in due:
        scheduled_transfer_id = doc["scheduled_transfer_id"]
        execute_at = doc["execute_at"]

        # Fire-window check. A transfer whose window has passed is not
        # fired — it's marked FAILED with reason EXPIRED. An outage
        # that resumes must not cause a burst of stale transfers to
        # execute all at once.
        if execute_at < (now - window):
            logger.warning(
                "Scheduled transfer id=%s is stale (execute_at=%s, "
                "now=%s); marking EXPIRED.",
                scheduled_transfer_id,
                execute_at.isoformat(),
                now.isoformat(),
            )
            _mark_failed(
                scheduled_transfer_id,
                failure_reason="SCHEDULED_TRANSFER_EXPIRED",
            )
            processed += 1
            continue

        _fire_one(doc)
        processed += 1

    return processed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fire_one(doc: dict[str, Any]) -> None:
    """Fire a single due transfer.

    Runs the transfer through ``execute_pre_authorized`` — the PIN was
    verified at scheduling time and is not re-checked. Records the
    outcome on the scheduled-transfer document.

    Error handling is split three ways:

        * ``DuplicateTransferError`` — a *previous* scheduler pass
          already settled this scheduled transfer under our
          deterministic idempotency key but was interrupted before
          ``mark_settled`` committed. Recovered by looking up the
          transaction id and marking the document SETTLED. This
          branch MUST come before the general ``NovaBanqError``
          handler: ``DuplicateTransferError`` is a 409, and without
          this branch it would be caught by the business-rejection
          path and recorded as a false FAILED.
        * Other ``NovaBanqError`` with ``status_code >= 500`` —
          infrastructure failure, transient. Re-raised so the next
          scheduler pass retries.
        * Other ``NovaBanqError`` with ``status_code < 500`` —
          business rejection, permanent. Recorded as
          ``failure_reason``.

    A lost race on ``mark_settled`` (the document was no longer
    PENDING when the money had already moved) is logged at CRITICAL.
    The two most plausible causes are a concurrent user cancel and a
    concurrent scheduler process; the log names both rather than
    assuming one.
    """
    scheduled_transfer_id = doc["scheduled_transfer_id"]
    uid = doc["uid"]
    recipient_tag = doc["recipient_tag"]
    amount_minor = doc["amount_minor"]

    # Deterministic idempotency key for the underlying ledger
    # transaction — same scheduled transfer, same key, so a retry of
    # this exact scheduled execution cannot settle twice. This holds
    # even if two scheduler processes fire the same due transfer
    # concurrently: both calls target the same ledger idempotency key,
    # the ledger deduplicates them, and only one commit happens.
    transfer_idempotency_key = f"scheduled-{scheduled_transfer_id}"

    try:
        result = transfers_service.execute_pre_authorized(
            sender_uid=uid,
            recipient_tag=recipient_tag,
            send_amount_minor=amount_minor,
            idempotency_key=transfer_idempotency_key,
        )
    except DuplicateTransferError:
        # The ledger already settled this scheduled transfer under our
        # deterministic idempotency key on a *previous* scheduler pass.
        # That pass moved the money but was interrupted before
        # ``mark_settled`` committed — so the document is still
        # PENDING even though the transfer succeeded. Recover by
        # looking up the transaction id and marking the scheduled
        # transfer SETTLED.
        _recover_settled(scheduled_transfer_id, transfer_idempotency_key)
        return
    except NovaBanqError as exc:
        if exc.status_code >= 500:
            # Infrastructure failure — transient. Re-raise so the next
            # scheduler pass retries this same transfer. Do NOT mark
            # the scheduled transfer FAILED; a Firestore or ledger
            # outage should not permanently fail due transfers.
            logger.warning(
                "Scheduled transfer id=%s hit a transient error "
                "(%s); leaving PENDING for retry on the next pass.",
                scheduled_transfer_id,
                exc.code.value,
            )
            raise

        # Business rejection — permanent for this attempt. Record
        # the error code so the user sees what went wrong.
        logger.info(
            "Scheduled transfer id=%s failed: [%s] %s",
            scheduled_transfer_id,
            exc.code.value,
            exc.message,
        )
        _mark_failed(
            scheduled_transfer_id,
            failure_reason=exc.code.value,
        )
        return

    logger.info(
        "Scheduled transfer id=%s settled; transaction_id=%s.",
        scheduled_transfer_id,
        result.transaction_id,
    )
    try:
        scheduled_repository.mark_settled(
            scheduled_transfer_id,
            transaction_id=result.transaction_id,
        )
    except ScheduledTransferStateError:
        # The document's status changed between list_due and now. The
        # money has already moved — this is a real anomaly. Two
        # plausible causes: (a) a user cancelled between our list_due
        # read and our mark_settled write, or (b) a second scheduler
        # process also picked up this due transfer. Both are worth
        # investigating; the log names both rather than assuming one.
        logger.critical(
            "Scheduled transfer id=%s settled (transaction_id=%s) but "
            "the document was no longer PENDING when we tried to mark "
            "it. Likely causes: a concurrent cancel raced the "
            "scheduler, or two scheduler processes both fired this "
            "transfer. Investigate which.",
            scheduled_transfer_id,
            result.transaction_id,
        )


def _recover_settled(
    scheduled_transfer_id: str,
    idempotency_key: str,
) -> None:
    """Recover from a settled-but-unmarked scheduled transfer.

    Called when ``execute_pre_authorized`` raises
    ``DuplicateTransferError`` — the ledger already committed the
    transfer under our deterministic idempotency key, but the
    scheduled-transfer document is still PENDING (the previous
    scheduler pass was interrupted between the ledger commit and
    ``mark_settled``). The transfer succeeded; the bookkeeping didn't.

    Looks up the transaction id from the idempotency record, then
    attempts to mark the scheduled transfer SETTLED. If a concurrent
    caller has already transitioned the document (e.g. a user
    cancelled while the recovery was in flight), the mark raises
    ``ScheduledTransferStateError`` and this function logs it at
    CRITICAL — the transfer settled but the document says otherwise,
    which is the anomaly worth investigating.

    Args:
        scheduled_transfer_id: The scheduled transfer to recover.
        idempotency_key: The deterministic key the underlying ledger
            transaction was committed under.
    """
    # First try the document itself — if a partial write already
    # populated transaction_id, use it.
    existing = scheduled_repository.get_by_id(scheduled_transfer_id)
    if existing is None:
        logger.critical(
            "Scheduled transfer id=%s raised DuplicateTransferError but "
            "no document exists. The ledger committed a transfer with "
            "no scheduled record; investigate.",
            scheduled_transfer_id,
        )
        return

    transaction_id = existing.get("transaction_id")
    if transaction_id is None:
        # The document was still PENDING (which is why we're here).
        # Look up the transaction id from the ledger's idempotency
        # record instead.
        try:
            transfer_doc = transfers_service.repository.get_by_idempotency_key(
                idempotency_key
            )
        except NovaBanqError:
            transfer_doc = None

        if transfer_doc is None:
            logger.critical(
                "Scheduled transfer id=%s raised DuplicateTransferError "
                "but the ledger idempotency record for key=%s is "
                "unreadable. Investigate — the money moved but we "
                "cannot find its transaction id.",
                scheduled_transfer_id,
                idempotency_key,
            )
            return
        transaction_id = transfer_doc.transaction_id

    try:
        scheduled_repository.mark_settled(
            scheduled_transfer_id,
            transaction_id=transaction_id,
        )
        logger.info(
            "Recovered scheduled transfer id=%s: settled on a prior "
            "pass; marked SETTLED with transaction_id=%s.",
            scheduled_transfer_id,
            transaction_id,
        )
    except ScheduledTransferStateError:
        logger.critical(
            "Scheduled transfer id=%s settled (transaction_id=%s) but "
            "the document was in a non-PENDING state when recovery "
            "tried to mark it. Likely causes: a concurrent cancel "
            "raced the scheduler, or a second scheduler already "
            "recovered this document.",
            scheduled_transfer_id,
            transaction_id,
        )


def _mark_failed(scheduled_transfer_id: str, *, failure_reason: str) -> None:
    """Mark a scheduled transfer FAILED, tolerating a lost race.

    The ``mark_failed`` call can lose a race to a concurrent cancel —
    the user cancelled while the scheduler was executing and failing.
    That's benign: the outcome is FAILED-or-CANCELLED, both terminal,
    and the money did not move. Log at info and move on.
    """
    try:
        scheduled_repository.mark_failed(
            scheduled_transfer_id,
            failure_reason=failure_reason,
        )
    except ScheduledTransferStateError:
        logger.info(
            "Scheduled transfer id=%s was already transitioned by a "
            "concurrent caller; the FAILED transition was skipped.",
            scheduled_transfer_id,
        )


def _scheduled_transfer_id_from_key(idempotency_key: str) -> str:
    """Derive a deterministic scheduled-transfer id from the client's key.

    UUIDv5 — deterministic, stable across calls, unique per key.

    A deterministic *document id* (not just an idempotency key) is
    required here because the repository's get-or-create targets a
    specific Firestore document; a random id would let two concurrent
    requests with the same key write two documents, and the
    transactional get-or-create would have no shared target to
    serialize on. The funding service solves the analogous problem in
    its ledger idempotency key with a plain f-string, because the
    ledger's own idempotency check operates on the key value, not on
    a document reference — different mechanism, same goal.
    """
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"novabanq-scheduled-{idempotency_key}")
    )


def _response_from_doc(
    doc: dict[str, Any],
    *,
    resolve_recipient_name: bool = False,
    recipient_display_name: str | None = None,
) -> ScheduledTransferResponse:
    """Project a stored scheduled-transfer document to the response model.

    Args:
        doc: The stored document.
        resolve_recipient_name: If True and ``recipient_display_name``
            is None, look up the recipient's current display name by
            tag. Used by the list and get endpoints. If the recipient
            has been deleted, the field is left as None.
        recipient_display_name: A pre-resolved display name, passed by
            callers (like ``schedule``) that already have the profile
            in hand. When provided, this takes precedence over
            ``resolve_recipient_name``.

    Returns:
        A populated ``ScheduledTransferResponse``.
    """
    if recipient_display_name is None and resolve_recipient_name:
        try:
            recipient_uid = tags_service.resolve_uid(doc["recipient_tag"])
            if recipient_uid is not None:
                profile = users_service.get_profile(recipient_uid)
                recipient_display_name = transfers_service._display_name(profile)  # noqa: SLF001
        except NovaBanqError:
            # Recipient deleted or lookup failed — leave the name None
            # rather than failing the whole response.
            recipient_display_name = None

    return ScheduledTransferResponse(
        scheduled_transfer_id=doc["scheduled_transfer_id"],
        recipient_tag=doc["recipient_tag"],
        recipient_display_name=recipient_display_name,
        amount_minor=doc["amount_minor"],
        sender_currency=Currency(doc["sender_currency"]),
        execute_at=doc["execute_at"],
        status=ScheduledTransferStatus(doc["status"]),
        transaction_id=doc.get("transaction_id"),
        failure_reason=doc.get("failure_reason"),
        created_at=doc["created_at"],
    )