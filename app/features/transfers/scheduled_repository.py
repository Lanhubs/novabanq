"""Scheduled-transfer repository.

Firestore access for the ``scheduled_transfers`` collection. One
document per scheduled transfer, keyed by the id the service
generates. Everything in this module is read/write against that one
collection — the ledger itself is untouched here, and the underlying
transfer is executed by the scheduler calling
``transfers_service.execute_pre_authorized``.

The repository knows nothing about PIN verification, currency
conversion, or idempotency-key derivation. It writes and reads
documents with a fixed shape, and translates Firestore errors into
``ScheduledTransferRepositoryError`` for the service to handle.

Atomicity note:
    Both the create path (``create_if_absent``) and every status
    transition (``mark_settled``, ``mark_failed``, ``mark_cancelled``)
    run inside a Firestore transaction via ``run_atomic``, which uses
    ``@firestore.transactional`` from the Google Cloud Firestore SDK
    (see ``app.infra.firestore``). The transitions enforce their
    precondition — the current status must be the one the caller
    expects — inside the transaction, so a status change committed
    concurrently by another caller is observed on retry and rejected
    rather than silently overwritten.

    This matters because two callers genuinely race on the same
    document: a user cancelling a PENDING transfer can interleave with
    the scheduler's ``list_due`` pass picking the same document up for
    execution. Without the precondition check, the two writes would
    land in either order and one would silently destroy the other's
    record — a settled transfer showing as CANCELLED with no
    transaction_id, or a cancelled transfer whose money went out
    anyway.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction

from app.core.constants import (
    Currency,
    ErrorCode,
    FirestoreCollection,
    ScheduledTransferStatus,
)
from app.core.exceptions import NovaBanqError
from app.infra.firestore import collection, document, run_atomic

logger = logging.getLogger(__name__)


class ScheduledTransferRepositoryError(NovaBanqError):
    """Raised when the scheduled-transfer repository can't complete a call."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Scheduled transfer service is temporarily unavailable."


class ScheduledTransferStateError(NovaBanqError):
    """Raised when a status transition is rejected by its precondition.

    Fires when a caller tries to apply a transition that isn't valid
    from the document's *current* status — e.g. cancelling a transfer
    that has already settled, or marking as settled a transfer that
    has already been cancelled. The race that motivates this class is
    between the scheduler (firing due transfers) and the cancel
    endpoint (stopping pending ones); the winner is decided inside the
    Firestore transaction, and the loser sees this error rather than
    silently clobbering the winner's write.

    Distinct from ``ScheduledTransferRepositoryError`` — that's an
    infrastructure failure (a Firestore outage), transient and worth
    retrying. This is a logical outcome: the transition was validly
    rejected because it no longer applies.
    """

    status_code = 409
    code = ErrorCode.VALIDATION_ERROR
    message = "This scheduled transfer has already been finalized."


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def create_if_absent(
    scheduled_transfer_id: str,
    *,
    uid: str,
    recipient_tag: str,
    amount_minor: int,
    sender_currency: Currency,
    execute_at: datetime,
) -> tuple[dict[str, Any], bool]:
    """Create a scheduled transfer, or return the existing one.

    Get-or-create semantics, inside a single Firestore transaction. Two
    concurrent calls for the same ``scheduled_transfer_id`` cannot both
    write — one commits, the other retries, sees the committed document,
    and returns it unchanged. The caller distinguishes "I created this"
    from "this already existed" via the returned boolean, and uses that
    to decide whether to consume a PIN attempt.

    Args:
        scheduled_transfer_id: Deterministic id derived by the service
            from the client's idempotency key.
        uid: The sender's Firebase uid.
        recipient_tag: Normalized recipient tag.
        amount_minor: Amount to send, in the sender's currency.
        sender_currency: The sender's currency at scheduling time.
        execute_at: When the transfer should run, UTC-aware.

    Returns:
        A ``(document, created)`` tuple. ``created`` is True if this
        call wrote the document, False if it already existed.

    Raises:
        ScheduledTransferRepositoryError: On any Firestore failure.
    """
    doc_ref = document(
        FirestoreCollection.SCHEDULED_TRANSFERS, scheduled_transfer_id
    )
    created = False

    def _operation(transaction: Transaction) -> dict[str, Any]:
        nonlocal created

        snapshot = doc_ref.get(transaction=transaction)
        if snapshot.exists:
            data = snapshot.to_dict() or {}
            data.setdefault("scheduled_transfer_id", scheduled_transfer_id)
            return data

        transaction.set(
            doc_ref,
            {
                "scheduled_transfer_id": scheduled_transfer_id,
                "uid": uid,
                "recipient_tag": recipient_tag,
                "amount_minor": amount_minor,
                "sender_currency": sender_currency.value,
                "execute_at": execute_at,
                "status": ScheduledTransferStatus.PENDING.value,
                "transaction_id": None,
                "failure_reason": None,
                "created_at": SERVER_TIMESTAMP,
            },
        )
        created = True

        # Return a shape consistent with what we wrote. ``created_at``
        # is a local approximation of the SERVER_TIMESTAMP sentinel —
        # see the funding repository for the same note. Nothing
        # downstream compares it against a re-read.
        return {
            "scheduled_transfer_id": scheduled_transfer_id,
            "uid": uid,
            "recipient_tag": recipient_tag,
            "amount_minor": amount_minor,
            "sender_currency": sender_currency.value,
            "execute_at": execute_at,
            "status": ScheduledTransferStatus.PENDING.value,
            "transaction_id": None,
            "failure_reason": None,
            "created_at": datetime.now(timezone.utc),
        }

    try:
        result = run_atomic(_operation)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to create scheduled_transfer id=%s.",
            scheduled_transfer_id,
        )
        raise ScheduledTransferRepositoryError() from exc

    if created:
        logger.info(
            "Created scheduled_transfer id=%s uid=%s execute_at=%s.",
            scheduled_transfer_id,
            uid,
            execute_at.isoformat(),
        )
    return result, created


def _transition(
    scheduled_transfer_id: str,
    *,
    expected_status: ScheduledTransferStatus,
    new_status: ScheduledTransferStatus,
    transaction_id: str | None,
    failure_reason: str | None,
    log_verb: str,
) -> None:
    """Apply a status transition, atomically and only from the expected status.

    The shared body of every ``mark_*`` function below. Reads the
    current status inside a transaction, verifies it matches the
    caller's expectation, and only then writes. If the current status
    is anything else — the document was concurrently settled, failed,
    or cancelled by another caller — raises
    ``ScheduledTransferStateError`` instead of overwriting.

    Args:
        scheduled_transfer_id: Which scheduled transfer to transition.
        expected_status: The status the caller requires the document to
            still be in. Any other value aborts the write.
        new_status: The status to write.
        transaction_id: The ledger transaction id to record, or None.
        failure_reason: The failure code to record, or None.
        log_verb: Human-readable verb for the success log line, e.g.
            "settled", "failed", "cancelled".

    Raises:
        ScheduledTransferStateError: If the document's current status
            isn't ``expected_status``, or the document doesn't exist.
        ScheduledTransferRepositoryError: On any Firestore failure.
    """
    doc_ref = document(
        FirestoreCollection.SCHEDULED_TRANSFERS, scheduled_transfer_id
    )

    def _operation(transaction: Transaction) -> None:
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise ScheduledTransferStateError(
                f"Scheduled transfer {scheduled_transfer_id!r} does not "
                "exist."
            )

        current = (snapshot.to_dict() or {}).get("status")
        if current != expected_status.value:
            raise ScheduledTransferStateError(
                f"Scheduled transfer {scheduled_transfer_id!r} is "
                f"{current!r}, not {expected_status.value!r}; the "
                f"{log_verb} transition does not apply."
            )

        transaction.update(
            doc_ref,
            {
                "status": new_status.value,
                "transaction_id": transaction_id,
                "failure_reason": failure_reason,
            },
        )

    try:
        run_atomic(_operation)
    except ScheduledTransferStateError:
        # Business outcome, not an infrastructure failure. Already
        # logged at the call site that decided to attempt the
        # transition; re-raising unchanged.
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to mark scheduled_transfer id=%s as %s.",
            scheduled_transfer_id,
            new_status.value,
        )
        raise ScheduledTransferRepositoryError() from exc

    logger.info(
        "Scheduled_transfer id=%s %s (from %s to %s).",
        scheduled_transfer_id,
        log_verb,
        expected_status.value,
        new_status.value,
    )


def mark_settled(
    scheduled_transfer_id: str,
    *,
    transaction_id: str,
) -> None:
    """Mark a scheduled transfer as settled after the ledger committed.

    Called by the scheduler immediately after
    ``transfers_service.execute_pre_authorized`` returns a settled
    result. Writes the underlying ``transaction_id`` so the frontend
    can link the scheduled transfer to its receipt.

    Only applies if the document is still ``PENDING``. If a concurrent
    cancel beat the scheduler to it, this raises
    ``ScheduledTransferStateError`` — the transfer has already moved
    money, so the caller (the scheduler) logs it as an anomalous
    outcome rather than retrying.

    Raises:
        ScheduledTransferStateError: If the document isn't PENDING, or
            doesn't exist.
        ScheduledTransferRepositoryError: On any Firestore failure.
    """
    _transition(
        scheduled_transfer_id,
        expected_status=ScheduledTransferStatus.PENDING,
        new_status=ScheduledTransferStatus.SETTLED,
        transaction_id=transaction_id,
        failure_reason=None,
        log_verb="settled",
    )


def mark_failed(
    scheduled_transfer_id: str,
    *,
    failure_reason: str,
) -> None:
    """Mark a scheduled transfer as failed.

    ``failure_reason`` is the error code that caused the failure —
    e.g. ``INSUFFICIENT_BALANCE``, ``RECIPIENT_NOT_FOUND``, or the
    scheduler's own ``SCHEDULED_TRANSFER_EXPIRED`` for a transfer
    whose fire window passed while the scheduler was down.

    Only applies if the document is still ``PENDING``.

    Raises:
        ScheduledTransferStateError: If the document isn't PENDING, or
            doesn't exist.
        ScheduledTransferRepositoryError: On any Firestore failure.
    """
    _transition(
        scheduled_transfer_id,
        expected_status=ScheduledTransferStatus.PENDING,
        new_status=ScheduledTransferStatus.FAILED,
        transaction_id=None,
        failure_reason=failure_reason,
        log_verb="failed",
    )


def mark_cancelled(scheduled_transfer_id: str) -> None:
    """Mark a scheduled transfer as cancelled.

    Only applies if the document is still ``PENDING``. This is the
    point of the precondition check: cancelling a transfer that has
    already been settled (by the scheduler winning the race) must
    raise rather than null out the ``transaction_id`` and lose the
    audit link to money that has already moved.

    Raises:
        ScheduledTransferStateError: If the document isn't PENDING, or
            doesn't exist. The caller surfaces this to the user as
            "this transfer has already been finalized."
        ScheduledTransferRepositoryError: On any Firestore failure.
    """
    _transition(
        scheduled_transfer_id,
        expected_status=ScheduledTransferStatus.PENDING,
        new_status=ScheduledTransferStatus.CANCELLED,
        transaction_id=None,
        failure_reason=None,
        log_verb="cancelled",
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_by_id(scheduled_transfer_id: str) -> dict[str, Any] | None:
    """Return a scheduled transfer by id, or None if it doesn't exist.

    Raises:
        ScheduledTransferRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(
            FirestoreCollection.SCHEDULED_TRANSFERS, scheduled_transfer_id
        ).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to read scheduled_transfer id=%s.",
            scheduled_transfer_id,
        )
        raise ScheduledTransferRepositoryError() from exc

    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    data.setdefault("scheduled_transfer_id", scheduled_transfer_id)
    return data


def list_for_user(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return the user's scheduled transfers, newest first.

    Requires a composite index on
    (``uid`` ASC, ``created_at`` DESC) — an equality filter on one
    field combined with an order-by on a different field needs one.
    Create the index before deploying; without it the query fails at
    call time with a Firestore error naming the missing index.

    Args:
        uid: Firebase uid of the caller.
        limit: Maximum number of documents to return. Defaults to 50 —
            a user's scheduled-transfer list is small.

    Returns:
        A list of scheduled-transfer documents. Returns an empty list
        if the user has none.

    Raises:
        ScheduledTransferRepositoryError: On any Firestore read failure.
    """
    try:
        snapshots = (
            collection(FirestoreCollection.SCHEDULED_TRANSFERS)
            .where("uid", "==", uid)
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to list scheduled transfers for uid=%s.", uid
        )
        raise ScheduledTransferRepositoryError() from exc

    # Preserve the document id from the snapshot itself before
    # discarding it — the fallback is only useful if we still know what
    # to fall back to.
    docs: list[dict[str, Any]] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        data.setdefault("scheduled_transfer_id", snapshot.id)
        docs.append(data)
    return docs


def list_due(now: datetime, limit: int) -> list[dict[str, Any]]:
    """Return scheduled transfers whose ``execute_at`` has passed.

    Used by the scheduler. Filters on ``status == PENDING`` and
    ``execute_at <= now``, ordered by ``execute_at`` ascending so the
    oldest due items are handled first.

    Requires a composite index on
    (``status`` ASC, ``execute_at`` ASC). Create it before deploying
    the scheduler; without it this query fails at call time.

    Args:
        now: The current time, UTC-aware. Transfers whose
            ``execute_at`` is at or before this instant are returned.
        limit: Maximum number of documents to return. Caps the batch
            size per scheduler pass.

    Returns:
        A list of due scheduled-transfer documents.

    Raises:
        ScheduledTransferRepositoryError: On any Firestore read failure.
    """
    try:
        snapshots = (
            collection(FirestoreCollection.SCHEDULED_TRANSFERS)
            .where("status", "==", ScheduledTransferStatus.PENDING.value)
            .where("execute_at", "<=", now)
            .order_by("execute_at", direction="ASCENDING")
            .limit(limit)
            .stream()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list due scheduled transfers.")
        raise ScheduledTransferRepositoryError() from exc

    docs: list[dict[str, Any]] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        data.setdefault("scheduled_transfer_id", snapshot.id)
        docs.append(data)
    return docs