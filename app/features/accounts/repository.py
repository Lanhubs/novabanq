"""Account repository.

Data access layer for the ``accounts`` Firestore collection. One
document per user, keyed by their Firebase uid. The document holds the
user's single currency wallet — the currency is fixed at creation and
never changes.

This module is deliberately narrow:
    * It reads accounts.
    * It creates accounts once, atomically, with a zero balance.

Writes to ``balance_minor`` in this module happen exactly once per
account — the initial zero, at creation. Every subsequent change to an
existing balance goes through the ledger module, which is the sole
writer of that field after this file creates the document. Any change
to an existing balance that is not visible in the ledger is a bug.

Errors from the underlying Firestore client are translated into
``AccountRepositoryError`` so callers never need to know about
``google.api_core`` specifics.
"""

import logging
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction

from app.core.constants import ErrorCode, FirestoreCollection
from app.core.exceptions import NovaBanqError
from app.infra.firestore import document, run_atomic

logger = logging.getLogger(__name__)


class AccountRepositoryError(NovaBanqError):
    """Raised when the account repository cannot complete an operation."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Account service is temporarily unavailable."


def get(uid: str) -> dict[str, Any] | None:
    """Return the account document for a uid, or None if absent.

    Absence is a normal state — a user who has never opened the app
    has no account yet.

    Raises:
        AccountRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(FirestoreCollection.ACCOUNTS, uid).get()
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception("Failed to read account for uid=%s.", uid)
        raise AccountRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    data.setdefault("uid", uid)
    return data


def get_or_create(uid: str, currency: str) -> dict[str, Any]:
    """Return the account for a uid, creating it if it does not exist.

    Atomic. The read and the write happen inside a single Firestore
    transaction, so two concurrent requests for the same uid cannot
    both create the document. The first commits; the second sees the
    existing document and returns it unchanged.

    If the account does not exist, it is created with
    ``balance_minor = 0``. That is the only time this module ever
    writes the field. All subsequent changes are made by the ledger.

    Args:
        uid: Firebase uid of the account owner.
        currency: The user's own currency (NGN, GHS, KES, XOF, ZAR).
            Ignored if the account already exists.

    Returns:
        The existing or newly created account document.

    Raises:
        AccountRepositoryError: On any Firestore failure.
    """
    account_ref = document(FirestoreCollection.ACCOUNTS, uid)
    created = False

    def _operation(transaction: Transaction) -> dict[str, Any]:
        nonlocal created

        # Reads must happen before writes in a Firestore transaction.
        snapshot = account_ref.get(transaction=transaction)

        if snapshot.exists:
            data = snapshot.to_dict() or {}
            data.setdefault("uid", uid)
            return data

        payload = {
            "uid": uid,
            "currency": currency,
            "balance_minor": 0,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
        transaction.set(account_ref, payload)
        created = True

        # Return a snapshot consistent with what we wrote. The
        # timestamps are SERVER_TIMESTAMP sentinels until the write
        # commits; callers that need them should re-read. Returning
        # the currency and zero balance is enough for the response.
        return {
            "uid": uid,
            "currency": currency,
            "balance_minor": 0,
        }

    try:
        result = run_atomic(_operation)
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception("Failed to get or create account for uid=%s.", uid)
        raise AccountRepositoryError() from exc

    if created:
        logger.info("Created account for uid=%s currency=%s.", uid, currency)

    return result