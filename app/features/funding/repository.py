"""Funding repository.

Firestore access for the funding feature. Two collections are touched:

    * ``funding_records/{uid}`` — one document per user holding their
      virtual account details. This is the source of truth for "does
      this user have a virtual account, and what are its details."
    * ``virtual_account_refs/{provider_ref}`` — reverse lookup from
      the provider's opaque reference back to the uid that owns the
      account. Keyed by the provider_ref, so the webhook's lookup is
      a direct document read, not a query.

The two documents are always written together, inside a single
Firestore transaction on ``funding_records/{uid}``. This makes the
get-or-create race-free (two concurrent creates cannot both see "no
record" and both write) and atomic (a crash between the two writes
cannot leave one document without the other).

Balance mutation happens in the ledger, never here. This repository
only manages the mapping between a user, their virtual account
details, and the provider's reference to it.

Firestore errors become ``FundingRepositoryError`` (a ``NovaBanqError``
subclass, 502), matching every other repository in this codebase.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP, Transaction

from app.core.constants import (
    Country,
    Currency,
    ErrorCode,
    FirestoreCollection,
)
from app.core.exceptions import NovaBanqError
from app.infra.firestore import document, run_atomic

logger = logging.getLogger(__name__)


class FundingRepositoryError(NovaBanqError):
    """Raised when the funding repository cannot complete an operation."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Funding service is temporarily unavailable."


# ---------------------------------------------------------------------------
# funding_records/{uid}
# ---------------------------------------------------------------------------

def get_funding_record(uid: str) -> dict[str, Any] | None:
    """Return the user's funding record, or None if they have none.

    Absence means the user has never created a virtual account. That
    is a normal state — the funding service calls ``get_or_create``
    on first ``POST /funding/virtual-account``.

    This read is unconditional and outside any transaction. Callers
    that only need to *read* (a status check, a debugging endpoint)
    use this. Callers that need to *create if absent* use
    ``get_or_create``, which reads inside a transaction to avoid a
    race.

    Raises:
        FundingRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(FirestoreCollection.FUNDING_RECORDS, uid).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read funding record for uid=%s.", uid)
        raise FundingRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    data.setdefault("uid", uid)
    return data


def get_or_create(
    uid: str,
    *,
    account_number: str,
    bank_name: str,
    account_name: str,
    currency: Currency,
    country: Country,
    provider_ref: str,
) -> tuple[dict[str, Any], bool]:
    """Return the user's funding record, creating it if absent.

    Atomic and race-free. Both the read (does a record exist?) and
    the two writes (the funding record and the reverse-lookup
    document) happen inside a single Firestore transaction. Two
    concurrent calls for the same uid cannot both see "no record" —
    one commits, the other retries, sees the committed record, and
    returns it unchanged.

    If a record already exists, the arguments are ignored and the
    existing record is returned with ``created=False``. This mirrors
    ``accounts.repository.get_or_create`` — same get-or-create shape,
    same transaction protection.

    Args:
        uid: Firebase uid of the account owner.
        account_number: Virtual account number from the provider.
        bank_name: Provider's bank name for display.
        account_name: Name on the account (the user's display name).
        currency: The account's currency.
        country: The account's country.
        provider_ref: The provider's opaque reference for this
            account. Written to ``virtual_account_refs`` as the key
            of the reverse-lookup document.

    Returns:
        A ``(record, created)`` tuple. ``record`` is the stored
        funding document; ``created`` is True if this call created
        it, False if it already existed.

    Raises:
        FundingRepositoryError: On any Firestore failure.
    """
    funding_ref = document(FirestoreCollection.FUNDING_RECORDS, uid)
    refs_ref = document(FirestoreCollection.VIRTUAL_ACCOUNT_REFS, provider_ref)
    created = False

    def _operation(transaction: Transaction) -> dict[str, Any]:
        nonlocal created

        # Reads must happen before writes in a Firestore transaction.
        snapshot = funding_ref.get(transaction=transaction)

        if snapshot.exists:
            data = snapshot.to_dict() or {}
            data.setdefault("uid", uid)
            return data

        # No record exists yet. Write both documents in the same
        # transaction so a crash between them is impossible, and so
        # two concurrent transactions cannot both reach this branch.
        transaction.set(
            funding_ref,
            {
                "uid": uid,
                "account_number": account_number,
                "bank_name": bank_name,
                "account_name": account_name,
                "currency": currency.value,
                "country": country.value,
                "provider_ref": provider_ref,
                "created_at": SERVER_TIMESTAMP,
            },
        )
        transaction.set(
            refs_ref,
            {
                "uid": uid,
                "provider_ref": provider_ref,
                "created_at": SERVER_TIMESTAMP,
            },
        )
        created = True

        # Return a snapshot consistent with what we wrote. The
        # timestamps are SERVER_TIMESTAMP sentinels until the write
        # commits; callers that need the real value should re-read.
        # ``VirtualAccountResponse.created_at`` is populated from a
        # local approximation by the service — see the service
        # docstring for why that is acceptable.
        return {
            "uid": uid,
            "account_number": account_number,
            "bank_name": bank_name,
            "account_name": account_name,
            "currency": currency.value,
            "country": country.value,
            "provider_ref": provider_ref,
            "created_at": datetime.now(timezone.utc),
        }

    try:
        record = run_atomic(_operation)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to get or create funding record for uid=%s.", uid)
        raise FundingRepositoryError() from exc

    if created:
        logger.info(
            "Created funding record for uid=%s provider_ref=%s.",
            uid,
            provider_ref,
        )

    return record, created


# ---------------------------------------------------------------------------
# virtual_account_refs/{provider_ref}
# ---------------------------------------------------------------------------

def get_uid_for_ref(provider_ref: str) -> str | None:
    """Return the uid that owns a provider reference.

    Returns ``None`` when the reference is unknown — the webhook
    receives a reference that does not correspond to any virtual
    account we issued. That is treated as a data integrity issue at
    the service layer, not a business outcome: a real Flutterwave
    webhook will only ever reference accounts we created.

    Raises:
        FundingRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(
            FirestoreCollection.VIRTUAL_ACCOUNT_REFS, provider_ref
        ).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to read ref mapping for provider_ref=%s.",
            provider_ref,
        )
        raise FundingRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    uid = data.get("uid")
    if not isinstance(uid, str) or not uid:
        logger.error(
            "Ref mapping for provider_ref=%s exists but has no uid.",
            provider_ref,
        )
        return None
    return uid