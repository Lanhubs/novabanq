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

from app.core.constants import FirestoreCollection
from app.infra.firestore import document, run_atomic

logger = logging.getLogger(__name__)


def get_by_tag(tag: str) -> dict[str, Any] | None:
    """Return the tag document for the given tag, or None if unclaimed."""
    snapshot = document(FirestoreCollection.TAGS, tag).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def exists(tag: str) -> bool:
    """Return True if the tag is already claimed."""
    return get_by_tag(tag) is not None


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

    run_atomic(_operation)

    if claimed:
        logger.info("Reserved tag '@%s' for uid=%s.", tag, uid)
    else:
        logger.info("Tag '@%s' already owned by another uid.", tag)

    return claimed