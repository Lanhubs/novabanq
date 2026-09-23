"""Account number repository.

Data access layer for the ``account_numbers`` Firestore collection.
Each document maps a generated account number to the uid that owns it,
enabling O(1) uniqueness checks and reverse lookups (account number →
uid).

Race-safety:
    The reserve operation reads and writes within a single Firestore
    transaction. Firestore guarantees serializable isolation for
    transactions, so two concurrent requests to claim the same number
    cannot both succeed — one commits, the other retries, sees the
    committed document, and fails the uniqueness check.
"""

import logging
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction

from app.core.constants import FirestoreCollection
from app.infra.firestore import document, run_atomic

logger = logging.getLogger(__name__)


def get_by_number(account_number: str) -> dict[str, Any] | None:
    """Return the account-number document for the given number.

    Args:
        account_number: The full NovaBanq account number (e.g. "NB0147293810").

    Returns:
        The document data with ``uid`` and ``created_at`` fields, or
        ``None`` if the number has not been issued.
    """
    snapshot = document(FirestoreCollection.ACCOUNT_NUMBERS, account_number).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def number_exists(account_number: str) -> bool:
    """Return True if the account number has already been issued."""
    return get_by_number(account_number) is not None


def reserve_atomic(account_number: str, uid: str) -> bool:
    """Claim an account number for a uid inside a Firestore transaction.

    The read and the write happen inside a single transaction. If
    another request commits the same number first, this call's
    transaction is retried by the Firestore client, and on retry the
    document will already exist with a different owner — in which case
    this function returns False and performs no write.

    Args:
        account_number: The full NovaBanq account number.
        uid: The Firebase uid of the owner.

    Returns:
        True if the number was reserved by this call.
        False if the number already exists and is owned by a different uid.
    """
    number_ref = document(FirestoreCollection.ACCOUNT_NUMBERS, account_number)
    claimed = False

    def _operation(transaction: Transaction) -> None:
        nonlocal claimed

        # All reads must occur before any writes in a Firestore
        # transaction. Do the read first, then decide whether to write.
        snapshot = number_ref.get(transaction=transaction)

        if snapshot.exists:
            existing_uid = (snapshot.to_dict() or {}).get("uid")
            if existing_uid != uid:
                # Taken by someone else. Do not write.
                claimed = False
                return

        # Either the number is new or it already belongs to this uid —
        # either way, idempotently set the document to this owner.
        transaction.set(
            number_ref,
            {
                "uid": uid,
                "created_at": SERVER_TIMESTAMP,
            },
        )
        claimed = True

    run_atomic(_operation)

    if claimed:
        logger.info(
            "Reserved account number %s for uid=%s.",
            account_number,
            uid,
        )
    else:
        logger.info("Account number %s already owned by another uid.", account_number)

    return claimed