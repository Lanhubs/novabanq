"""Transactions repository.

Read access to the ``transactions`` collection, scoped to what a
user's history and receipts need. Writes never happen here — the
ledger owns every write, and this module exists only so the
transactions service can read what the ledger produced.

Three functions:

    * ``list_for_sender(uid, limit)`` — transactions the user sent.
    * ``list_for_recipient(uid, limit)`` — transactions the user
      received.
    * ``get_by_id(transaction_id)`` — a single transaction by id, for
      the receipt endpoint.

The two list functions deliberately do not paginate at this layer.
The service merges their results and applies the page window itself,
because the merge has to happen in Python anyway (Firestore can't
sort across two disjoint queries). Paginating inside the repository
would produce a merged result that's wrong at page boundaries.

Note for whoever writes that merge: self-transfers are rejected today
by the validator, not by anything in this schema, so
``list_for_sender`` and ``list_for_recipient`` could in principle both
return the same document if a future transaction type ever allowed
``sender_uid == recipient_uid``. The merge should de-duplicate by
``transaction_id`` rather than assuming the two result sets are
disjoint.

Firestore errors become ``TransactionRepositoryError`` (a
``NovaBanqError`` subclass, 502), matching every other repository in
this codebase.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.constants import (
    Currency,
    ErrorCode,
    FirestoreCollection,
    TransactionStatus,
    TransactionType,
)
from app.core.exceptions import NovaBanqError
from app.features.ledger.schemas import TransactionDocument
from app.infra.firestore import collection, document

logger = logging.getLogger(__name__)


class TransactionRepositoryError(NovaBanqError):
    """Raised when the transactions repository cannot complete a read."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Transaction service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_for_sender(uid: str, limit: int) -> list[TransactionDocument]:
    """Return transactions the uid sent, newest first.

    Filters on ``sender_uid == uid``. Includes outbound TRANSFERs and
    WITHDRAWALs; excludes FUNDING (which has no sender) and any
    transaction where the caller was only the recipient.

    Requires a Firestore composite index on
    (``sender_uid`` ASC, ``created_at`` DESC) — an equality filter on
    one field combined with an order-by on a different field needs
    one. Without it, this query fails at call time with a Firestore
    error naming the missing index, not at import time, so create the
    index before this ships rather than discovering it from a
    production error.

    Args:
        uid: Firebase uid of the caller.
        limit: Maximum number of documents to return. The service
            typically passes ``limit * 2`` so it has enough to merge
            with the recipient-side results and still yield a full
            page.

    Returns:
        A list of parsed ``TransactionDocument`` objects, ordered by
        ``created_at`` descending. May be shorter than ``limit`` if
        the user has fewer transactions on that side.

    Raises:
        TransactionRepositoryError: On a Firestore read failure, or
            if any returned document is corrupt.
    """
    try:
        snapshots = (
            collection(FirestoreCollection.TRANSACTIONS)
            .where("sender_uid", "==", uid)
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        raw_docs = [s.to_dict() or {} for s in snapshots]
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to list sent transactions for uid=%s.", uid
        )
        raise TransactionRepositoryError() from exc

    return _parse_many(raw_docs)


def list_for_recipient(uid: str, limit: int) -> list[TransactionDocument]:
    """Return transactions the uid received, newest first.

    Filters on ``recipient_uid == uid``. Includes inbound TRANSFERs and
    FUNDINGs; excludes WITHDRAWAL (which has no recipient) and any
    transaction where the caller was only the sender.

    Requires a Firestore composite index on
    (``recipient_uid`` ASC, ``created_at`` DESC), for the same reason
    as ``list_for_sender``.

    Args:
        uid: Firebase uid of the caller.
        limit: Maximum number of documents to return.

    Returns:
        A list of parsed ``TransactionDocument`` objects, ordered by
        ``created_at`` descending.

    Raises:
        TransactionRepositoryError: On a Firestore read failure, or
            if any returned document is corrupt.
    """
    try:
        snapshots = (
            collection(FirestoreCollection.TRANSACTIONS)
            .where("recipient_uid", "==", uid)
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        raw_docs = [s.to_dict() or {} for s in snapshots]
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to list received transactions for uid=%s.", uid
        )
        raise TransactionRepositoryError() from exc

    return _parse_many(raw_docs)


def get_by_id(transaction_id: str) -> TransactionDocument | None:
    """Read a transaction document by id, or None if it doesn't exist.

    Args:
        transaction_id: The ledger transaction identifier.

    Returns:
        A parsed ``TransactionDocument``, or ``None`` when no document
        exists for that id.

    Raises:
        TransactionRepositoryError: On a Firestore read failure, or if
            the stored document is corrupt.
    """
    try:
        snapshot = document(
            FirestoreCollection.TRANSACTIONS,
            transaction_id,
        ).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to read transaction %s.", transaction_id
        )
        raise TransactionRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    return _parse_transaction(data, transaction_id)


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------

def _parse_many(raw_docs: list[dict[str, Any]]) -> list[TransactionDocument]:
    """Parse a batch of documents, skipping any that fail to parse.

    A single corrupt document shouldn't take down a user's whole
    history. This catches both the specific, expected failure mode
    (``TransactionRepositoryError`` — a known validation failure, e.g.
    a missing field or an unrecognised enum value) and any genuinely
    unexpected exception, logged separately so the two stay
    distinguishable. Catching only the former would leave a gap: a
    truly unanticipated failure in one document would still propagate
    out of this loop and take down the entire listing for every other
    transaction in the batch — precisely what this function exists to
    prevent. If every entry turns out to be corrupt, the caller gets
    an empty list, never an exception.

    Individual reads (``get_by_id``) are strict — see
    ``_parse_transaction`` — because a receipt for a corrupt
    transaction is worse than an error.
    """
    parsed: list[TransactionDocument] = []
    for raw in raw_docs:
        transaction_id = raw.get("transaction_id", "<unknown>")
        try:
            parsed.append(_parse_transaction(raw, transaction_id))
        except TransactionRepositoryError:
            logger.error(
                "Skipping unparseable transaction %s in history list.",
                transaction_id,
            )
        except Exception:  # noqa: BLE001 — see docstring above
            logger.exception(
                "Skipping transaction %s in history list due to an "
                "unexpected parsing error.",
                transaction_id,
            )
    return parsed


def _parse_transaction(
    data: dict[str, Any],
    transaction_id: str,
) -> TransactionDocument:
    """Reconstruct a ``TransactionDocument`` from Firestore storage.

    Mirrors the parsing logic in ``transfers/repository.py`` — same
    field names, same enum coercions, same nullability. Deliberately
    duplicated rather than shared: the two modules have different
    error types (``TransferRepositoryError`` vs.
    ``TransactionRepositoryError``) and different skip-vs-fail
    behaviour, and folding them together would require a third shared
    module just to pick which error to raise.

    Raises:
        TransactionRepositoryError: If any required field is missing
            or cannot be interpreted.
    """
    try:
        return TransactionDocument(
            transaction_id=_require_str(data, "transaction_id", transaction_id),
            transaction_type=_require_enum(
                data, "transaction_type", TransactionType, transaction_id
            ),
            status=_require_enum(
                data, "status", TransactionStatus, transaction_id
            ),
            idempotency_key=_require_str(
                data, "idempotency_key", transaction_id
            ),
            sender_uid=_optional_str(data, "sender_uid"),
            recipient_uid=_optional_str(data, "recipient_uid"),
            sender_snapshot=_optional_snapshot(data, "sender_snapshot"),
            recipient_snapshot=_optional_snapshot(
                data, "recipient_snapshot"
            ),
            from_currency=_optional_currency(
                data, "from_currency", transaction_id
            ),
            to_currency=_optional_currency(
                data, "to_currency", transaction_id
            ),
            from_amount_minor=_optional_int(data, "from_amount_minor"),
            to_amount_minor=_optional_int(data, "to_amount_minor"),
            fee_minor=_require_int(data, "fee_minor", transaction_id),
            rate_scaled=_optional_int(data, "rate_scaled"),
            created_at=_require_datetime(data, "created_at", transaction_id),
            settled_at=_optional_datetime(data, "settled_at"),
        )
    except TransactionRepositoryError:
        raise
    except (ValueError, TypeError) as exc:
        logger.exception(
            "Stored transaction %s failed invariant checks.",
            transaction_id,
        )
        raise TransactionRepositoryError() from exc


def _require_str(
    data: dict[str, Any],
    key: str,
    transaction_id: str,
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        logger.error(
            "Transaction %s is missing or has an invalid %s.",
            transaction_id,
            key,
        )
        raise TransactionRepositoryError()
    return value


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return value


def _require_int(
    data: dict[str, Any],
    key: str,
    transaction_id: str,
) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        logger.error(
            "Transaction %s is missing or has an invalid %s.",
            transaction_id,
            key,
        )
        raise TransactionRepositoryError()
    return value


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def _require_enum(
    data: dict[str, Any],
    key: str,
    enum_cls: type,
    transaction_id: str,
) -> Any:
    raw = data.get(key)
    if raw is None:
        logger.error(
            "Transaction %s is missing %s.", transaction_id, key
        )
        raise TransactionRepositoryError()
    try:
        return enum_cls(raw)
    except ValueError:
        logger.error(
            "Transaction %s holds an unrecognised %s value %r.",
            transaction_id,
            key,
            raw,
        )
        raise TransactionRepositoryError() from None


def _optional_currency(
    data: dict[str, Any],
    key: str,
    transaction_id: str,
) -> Currency | None:
    raw = data.get(key)
    if raw is None:
        return None
    try:
        return Currency(raw)
    except ValueError:
        logger.error(
            "Transaction %s holds an unrecognised %s value %r.",
            transaction_id,
            key,
            raw,
        )
        raise TransactionRepositoryError() from None


def _optional_snapshot(
    data: dict[str, Any],
    key: str,
) -> dict[str, str] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    # Pass through only the fields the snapshot is expected to carry.
    # The schema validates the shape on write; this read-side coercion
    # is deliberately forgiving so a future added field doesn't break
    # existing records. If either tag or name is missing or not a
    # string, treat the whole snapshot as absent rather than returning
    # a partial dict — the return type promises both keys are valid
    # whenever the result isn't None, and the frontend falls back to
    # the uid when this returns None.
    tag = value.get("tag")
    name = value.get("name")
    if not isinstance(tag, str) or not isinstance(name, str):
        return None
    return {"tag": tag, "name": name}


def _require_datetime(
    data: dict[str, Any],
    key: str,
    transaction_id: str,
) -> datetime:
    value = data.get(key)
    if not isinstance(value, datetime):
        logger.error(
            "Transaction %s is missing or has an invalid %s.",
            transaction_id,
            key,
        )
        raise TransactionRepositoryError()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _optional_datetime(
    data: dict[str, Any],
    key: str,
) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value