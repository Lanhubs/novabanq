"""Transfer repository.

Read access to the ``transactions`` collection, scoped to what the
transfers feature needs. Writes never happen here — the ledger owns
every write to ``transactions``, and this module exists only so the
transfers service can look up a transaction it just created (or a
prior one, by id) without reaching into the ledger's repository.

Two functions:

    * ``get_by_id(transaction_id)`` — read a single transaction
      document, parsed into the ``TransactionDocument`` dataclass.
    * ``get_by_idempotency_key(key)`` — read the transaction a key
      maps to, by first looking up the idempotency record. Used by the
      service to short-circuit a retry without going through the full
      ledger transaction.

Firestore errors become ``TransferRepositoryError`` (a ``NovaBanqError``
subclass, 502), matching the pattern of every other repository in this
codebase.
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
from app.infra.firestore import document

logger = logging.getLogger(__name__)


class TransferRepositoryError(NovaBanqError):
    """Raised when the transfers repository cannot complete a read."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Transaction service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_by_id(transaction_id: str) -> TransactionDocument | None:
    """Read a transaction document by id, or None if it doesn't exist.

    Args:
        transaction_id: The ledger transaction identifier.

    Returns:
        A parsed ``TransactionDocument``, or ``None`` when no document
        exists for that id.

    Raises:
        TransferRepositoryError: On a Firestore read failure, or if the
            stored document is corrupt and cannot be parsed.
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
        raise TransferRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    return _parse_transaction(data, transaction_id)


def get_by_idempotency_key(
    idempotency_key: str,
) -> TransactionDocument | None:
    """Read the transaction a client key maps to, if any.

    Two Firestore reads: first the idempotency record, then the
    transaction document it points to. Returns ``None`` only when the
    idempotency record itself doesn't exist — an unused key is a
    normal state, not an error. Once a record is found, it must
    resolve to a real, readable transaction; anything else is treated
    as corruption, not as "key unused" (see Raises below for why).

    Args:
        idempotency_key: A validated client idempotency key.

    Returns:
        The parsed ``TransactionDocument`` for the key's transaction,
        or ``None`` if the key has never been used.

    Raises:
        TransferRepositoryError: On any Firestore read failure, or if
            the idempotency record is corrupt — it holds a malformed
            id, or it holds a well-formed id that doesn't resolve to an
            existing transaction document.
    """
    try:
        key_snapshot = document(
            FirestoreCollection.IDEMPOTENCY_KEYS,
            idempotency_key,
        ).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read idempotency key for lookup.")
        raise TransferRepositoryError() from exc

    if not key_snapshot.exists:
        return None

    key_data: dict[str, Any] = key_snapshot.to_dict() or {}
    transaction_id = key_data.get("transaction_id")

    if not isinstance(transaction_id, str) or not transaction_id:
        # The idempotency record exists but is corrupt. This is a data
        # integrity bug — the ledger only ever writes a valid id here.
        # Fail loudly rather than returning None, because returning
        # None would let the service proceed to the ledger as if the
        # key were fresh. The ledger's own read would then find the
        # same corrupt record and raise there anyway; raising here
        # just gives the error an earlier, clearer origin.
        logger.error(
            "Idempotency record exists but holds no valid transaction_id."
        )
        raise TransferRepositoryError()

    transaction = get_by_id(transaction_id)
    if transaction is None:
        # The idempotency record points at a transaction_id with no
        # matching document. Under the ledger's write-once, single-shot
        # commit model, both documents are written in the same atomic
        # transaction — so this should be structurally impossible.
        # Treating it as "key unused" (returning None here) is exactly
        # the dangerous outcome the malformed-id check above exists to
        # prevent: the service would proceed as if this were a fresh
        # request and could move money again under a key that was
        # supposed to guarantee it wouldn't. Fail loudly instead.
        logger.error(
            "Idempotency key resolved to transaction_id=%s, but no "
            "matching transaction document exists.",
            transaction_id,
        )
        raise TransferRepositoryError()

    return transaction


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------

def _parse_transaction(
    data: dict[str, Any],
    transaction_id: str,
) -> TransactionDocument:
    """Reconstruct a ``TransactionDocument`` from Firestore storage.

    Every field that was stored as an enum's ``.value`` is coerced back
    through the enum. Missing or malformed fields raise
    ``TransferRepositoryError`` after a specific log line names the
    field, so a corrupt document is easy to find without re-running.

    The nullable fields — ``sender_uid``, ``recipient_uid``, the
    snapshots, and the from/to currency and amount pairs — are read
    as optional, since FUNDING and WITHDRAWAL legitimately have one
    side absent. The ``TransactionDocument`` dataclass itself validates
    what it can (positivity, the cross-currency/rate relationship when
    both sides are present) without guessing at the exact required
    combination per transaction type.

    Raises:
        TransferRepositoryError: If any required field is missing or
            cannot be interpreted.
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
    except TransferRepositoryError:
        raise
    except (ValueError, TypeError) as exc:
        # The dataclass's own __post_init__ validation, or a constructor
        # type error. Both mean the stored document violates an
        # invariant the ledger was supposed to enforce at write time.
        logger.exception(
            "Stored transaction %s failed invariant checks.",
            transaction_id,
        )
        raise TransferRepositoryError() from exc


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
        raise TransferRepositoryError()
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
        raise TransferRepositoryError()
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
        raise TransferRepositoryError()
    try:
        return enum_cls(raw)
    except ValueError:
        logger.error(
            "Transaction %s holds an unrecognised %s value %r.",
            transaction_id,
            key,
            raw,
        )
        raise TransferRepositoryError() from None


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
        raise TransferRepositoryError() from None


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
        raise TransferRepositoryError()
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