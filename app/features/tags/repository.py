"""Tag repository.

Data access layer for the ``tags`` Firestore collection. Each document
is keyed by the tag itself (lowercased, no leading '@'), which enforces
uniqueness at the database level: a document either exists or it does
not. There is no partial state.

Race-safety:
    The reserve operation reads and writes within a single Firestore
    transaction. Firestore guarantees serializable isolation for
    transactions, so two concurrent requests to claim the same tag
    cannot both succeed — one commits, the other retries, sees the
    committed document, and fails the uniqueness check.
"""

import logging
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction

from app.core.constants import ErrorCode, FirestoreCollection
from app.core.exceptions import NovaBanqError
from app.infra.firestore import document, run_atomic

logger = logging.getLogger(__name__)


class TagRepositoryError(NovaBanqError):
    """Raised when the tag repository cannot complete an operation.

    Wraps Firestore failures into a retryable outcome. Callers in
    higher layers translate this to whatever error class makes sense
    at their boundary — for example the transfers service treats a
    failed recipient-tag lookup the same way it treats "recipient not
    found", since from the sender's perspective both mean "we can't
    resolve who you're sending to right now".
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Tag service is temporarily unavailable."


def get_by_tag(tag: str) -> dict[str, Any] | None:
    """Return the tag document for the given tag, or None if unclaimed.

    Raises:
        TagRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(FirestoreCollection.TAGS, tag).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read tag %s.", tag)
        raise TagRepositoryError() from exc

    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def exists(tag: str) -> bool:
    """Return True if the tag is already claimed.

    Raises:
        TagRepositoryError: On any Firestore read failure.
    """
    return get_by_tag(tag) is not None


def get_uid_for_tag(tag: str) -> str | None:
    """Return the uid that owns the tag, or None if unclaimed.

    Used by the transfers service to resolve a recipient tag to the
    user who should receive the money. Reads the same tag-keyed
    document the reserve path writes, so a tag written by
    ``reserve_atomic`` is readable here without any extra index.

    Args:
        tag: The normalized tag (lowercase, no leading '@').

    Returns:
        The owning Firebase uid, or ``None`` if the tag has never been
        reserved.

    Raises:
        TagRepositoryError: On any Firestore read failure.
    """
    record = get_by_tag(tag)
    if record is None:
        return None
    uid = record.get("uid")
    return uid if isinstance(uid, str) and uid else None


def reserve_atomic(tag: str, uid: str) -> bool:
    """Reserve a tag for the given uid inside a Firestore transaction.

    The read and the write happen inside a single transaction. If
    another request commits the same tag first, this call's transaction
    is retried by the Firestore client, and on retry the document will
    already exist with a different owner — in which case this function
    returns False and performs no write.

    Args:
        tag: The normalized tag (lowercase, no leading '@').
        uid: The Firebase uid of the owner.

    Returns:
        True if the tag was reserved by this call.
        False if the tag already exists and is owned by a different uid.

    Raises:
        TagRepositoryError: On any Firestore failure.
    """
    tag_ref = document(FirestoreCollection.TAGS, tag)
    claimed = False

    def _operation(transaction: Transaction) -> None:
        nonlocal claimed

        # All reads must occur before any writes in a Firestore
        # transaction. Do the read first, then decide whether to write.
        snapshot = tag_ref.get(transaction=transaction)

        if snapshot.exists:
            existing_uid = (snapshot.to_dict() or {}).get("uid")
            if existing_uid != uid:
                # Taken by someone else. Do not write.
                claimed = False
                return

        # Either the tag is new or it already belongs to this uid —
        # either way, idempotently set the document to this owner.
        transaction.set(
            tag_ref,
            {
                "uid": uid,
                "created_at": SERVER_TIMESTAMP,
            },
        )
        claimed = True

    try:
        run_atomic(_operation)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to reserve tag '%s' for uid=%s.", tag, uid)
        raise TagRepositoryError() from exc

    if claimed:
        logger.info("Reserved tag '@%s' for uid=%s.", tag, uid)
    else:
        logger.info("Tag '@%s' already owned by another uid.", tag)

    return claimed