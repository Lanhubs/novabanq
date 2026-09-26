"""Transactions service.

Business logic for transaction history and receipts. Two entry points:

    * ``list_for_user(uid, limit)`` — a page of the user's
      transactions, newest first, merging sent and received sides.
    * ``get_receipt(transaction_id, uid)`` — full detail for one
      transaction, scoped to the caller's participation in it.

No HTTP. The router is thin and calls straight into these functions.

The merge in ``list_for_user`` is done in Python because the two
source queries — sent and received — are on disjoint filters and
Firestore cannot order across them. The repository fetches each side
already ordered by ``created_at`` descending; this layer merges them,
de-duplicates by ``transaction_id`` (see the repository docstring for
why that's necessary), trims to ``limit``, and produces the pagination
cursor.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from app.core.constants import ErrorCode
from app.core.exceptions import NovaBanqError
from app.features.ledger.schemas import TransactionDocument
from app.features.transactions import repository
from app.features.transactions.schemas import (
    TransactionListResponse,
    TransactionParty,
    TransactionSummary,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class TransactionNotFoundError(NovaBanqError):
    """Raised when a transaction id doesn't resolve to a document."""

    status_code = 404
    code = ErrorCode.TRANSACTION_NOT_FOUND
    message = "No transaction found with that id."


class TransactionAccessDeniedError(NovaBanqError):
    """Raised when a caller tries to read a transaction they're not on.

    Uses 404, not 403, so the endpoint doesn't leak the existence of
    other users' transactions. A caller who probes for random ids sees
    the same response whether the transaction exists and they're not
    on it, or doesn't exist at all.
    """

    status_code = 404
    code = ErrorCode.TRANSACTION_NOT_FOUND
    message = "No transaction found with that id."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_for_user(
    uid: str,
    *,
    limit: int = 20,
) -> TransactionListResponse:
    """Return one page of the user's transaction history.

    Merges sent and received sides, newest first. The two repository
    queries each fetch up to ``limit * 2`` documents so the merge has
    enough material to produce a full page even when one side is
    heavier than the other.

    Args:
        uid: Firebase uid of the caller.
        limit: Page size. Clamped to ``[1, 100]`` by the router.

    Returns:
        A ``TransactionListResponse`` with up to ``limit`` items and,
        if more exist, an opaque ``next_cursor``.
    """
    # Fetch enough from each side that the merge reliably yields a
    # full page. If one side dominates entirely, this over-fetches,
    # but at demo scale the cost is a couple of extra Firestore reads.
    fetch_limit = limit * 2

    sent = repository.list_for_sender(uid, fetch_limit)
    received = repository.list_for_recipient(uid, fetch_limit)

    merged = _merge_dedupe_sort(sent, received)

    page = merged[:limit]
    has_more = len(merged) > limit

    items = [_to_summary(doc, caller_uid=uid) for doc in page]

    next_cursor: str | None = None
    if has_more and page:
        # Cursor is the created_at of the last item in the page,
        # encoded as an ISO string. The service does not currently
        # accept a cursor on input — the list endpoint returns a
        # cursor the client can hold, but paging back into the past
        # requires the composite indexes the repository docstring
        # names, and that work is deferred. See the router for the
        # current behaviour.
        next_cursor = page[-1].created_at.isoformat()

    return TransactionListResponse(items=items, next_cursor=next_cursor)


def get_receipt(
    transaction_id: str,
    *,
    caller_uid: str,
) -> TransactionSummary:
    """Return one transaction, if the caller is a participant.

    Scoped: a caller who is neither the sender nor the recipient of
    the transaction gets the same 404 as if the id didn't exist. That
    prevents the endpoint from being used to enumerate other users'
    transaction ids.

    Args:
        transaction_id: The ledger transaction identifier.
        caller_uid: Firebase uid of the caller.

    Returns:
        A ``TransactionSummary`` describing the transaction from the
        caller's perspective.

    Raises:
        TransactionNotFoundError: If no transaction exists for the id,
            or the caller is not a participant.
    """
    doc = repository.get_by_id(transaction_id)
    if doc is None:
        raise TransactionNotFoundError()

    if caller_uid not in (doc.sender_uid, doc.recipient_uid):
        # Same error as "not found" — see the class docstring for why.
        raise TransactionAccessDeniedError()

    return _to_summary(doc, caller_uid=caller_uid)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge_dedupe_sort(
    sent: list[TransactionDocument],
    received: list[TransactionDocument],
) -> list[TransactionDocument]:
    """Merge two ordered lists, dedupe by id, sort descending.

    De-duplication matters because a transaction where the caller is
    both sender and recipient would appear in both source lists. Self-
    transfers are rejected by the validator today, but nothing in the
    schema prevents it — see the repository docstring — so the merge
    treats it as possible rather than assuming the two lists are
    disjoint.

    Sorting is done here rather than relying on either source's order
    because the two sources are only individually sorted; the merged
    stream is not. ``created_at`` is a timezone-aware datetime
    throughout, so a simple key sort is correct.
    """
    seen: set[str] = set()
    merged: list[TransactionDocument] = []

    for doc in sent + received:
        if doc.transaction_id in seen:
            continue
        seen.add(doc.transaction_id)
        merged.append(doc)

    merged.sort(key=_created_at_key, reverse=True)
    return merged


def _created_at_key(doc: TransactionDocument) -> datetime:
    """Sort key for ``created_at``, with a stable fallback.

    Every persisted transaction has ``created_at``, so the primary
    case never falls through. The fallback exists only so a
    hypothetical missing field doesn't crash the merge — a bug in the
    ledger's writes would surface as "this transaction sorts to the
    bottom", which is better than "the user's history is a 500".

    The fallback is deliberately ``datetime.min`` in UTC, matching the
    timezone normalization used everywhere else in this codebase
    (both transaction repositories, ``identity_repository.py``,
    ``account_service.py``). Using the server's local timezone here
    would compare incorrectly against the UTC ``created_at`` values on
    every other document, so the sort would be silently wrong by
    whatever offset the deployment happened to run in.
    """
    if doc.created_at is not None:
        return doc.created_at
    return datetime.min.replace(tzinfo=timezone.utc)


def _to_summary(
    doc: TransactionDocument,
    *,
    caller_uid: str,
) -> TransactionSummary:
    """Project a ``TransactionDocument`` to a ``TransactionSummary``.

    The projection is perspective-dependent: the same document yields
    ``direction == "OUT"`` for its sender and ``"IN"`` for its
    recipient. The counterparty is the *other* party — the recipient
    snapshot when the caller sent, the sender snapshot when the caller
    received. Neither party's own snapshot is ever echoed back.
    """
    direction, counterparty = _perspective(doc, caller_uid=caller_uid)

    return TransactionSummary(
        transaction_id=doc.transaction_id,
        transaction_type=doc.transaction_type,
        direction=direction,
        status=doc.status,
        counterparty=counterparty,
        from_currency=doc.from_currency,
        to_currency=doc.to_currency,
        from_amount_minor=doc.from_amount_minor,
        to_amount_minor=doc.to_amount_minor,
        fee_minor=doc.fee_minor,
        rate_scaled=doc.rate_scaled,
        created_at=doc.created_at,
    )


def _perspective(
    doc: TransactionDocument,
    *,
    caller_uid: str,
) -> tuple[Literal["IN", "OUT"], TransactionParty | None]:
    """Return (direction, counterparty) from the caller's point of view.

    Rules:

        * If the caller is the sender, direction is ``OUT`` and the
          counterparty is the recipient (if there is one — WITHDRAWAL
          has no recipient, so counterparty is None).
        * If the caller is the recipient, direction is ``IN`` and the
          counterparty is the sender (if there is one — FUNDING has
          no sender, so counterparty is None).
        * If the caller is both — possible only in theory — the
          direction is ``OUT``, matching how the transfer flow would
          present it to the user who initiated it.

    Raises:
        ValueError: If the caller is on neither side of the
            transaction. Both public entry points guard against this
            before calling, so reaching here is a caller bug. Raising
            rather than returning a default matches the convention
            used elsewhere in the codebase for "should never happen"
            branches — a silent wrong answer is worse than a loud
            500, especially in an authorization check.
    """
    is_sender = doc.sender_uid == caller_uid
    is_recipient = doc.recipient_uid == caller_uid

    if is_sender:
        # Outbound. Counterparty is the recipient, if there is one.
        if doc.recipient_uid is None:
            return "OUT", None
        return "OUT", _party_from_snapshot(
            uid=doc.recipient_uid,
            snapshot=doc.recipient_snapshot,
        )

    if is_recipient:
        # Inbound. Counterparty is the sender, if there is one.
        if doc.sender_uid is None:
            return "IN", None
        return "IN", _party_from_snapshot(
            uid=doc.sender_uid,
            snapshot=doc.sender_snapshot,
        )

    # Caller is on neither side. Both entry points guard against this
    # before calling (get_receipt raises TransactionAccessDeniedError,
    # list_for_user only ever fetches documents that match the caller),
    # so this branch is unreachable in practice. Raise rather than
    # returning a default — see the docstring.
    raise ValueError(
        f"_perspective called with caller_uid={caller_uid!r} who is "
        f"neither the sender nor the recipient of transaction "
        f"{doc.transaction_id!r}."
    )


def _party_from_snapshot(
    *,
    uid: str,
    snapshot: dict[str, str] | None,
) -> TransactionParty:
    """Build a ``TransactionParty`` from a uid and an optional snapshot.

    The snapshot is the best-effort record of the counterparty at
    settlement time. When it's missing or partial, the party is
    returned with ``tag`` and ``name`` as ``None`` — the uid is
    always populated because it's the field the ledger guarantees.
    """
    if snapshot is None:
        return TransactionParty(uid=uid, tag=None, name=None)
    return TransactionParty(
        uid=uid,
        tag=snapshot.get("tag"),
        name=snapshot.get("name"),
    )