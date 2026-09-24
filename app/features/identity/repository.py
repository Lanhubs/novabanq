"""Identity verification repository.

Data access layer for the ``identity_verifications`` Firestore
collection. One document per user, keyed by uid. Only the normalized
verification decision is stored — never the raw provider payload, never
the BVN in plaintext, never the face image.

The full BVN never leaves the adapter. Only the last four digits are
persisted, so a Firestore read cannot reconstruct a user's identity
number. This is a deliberate choice: an audit trail is useful, but
storing the raw BVN in Firestore without a retention policy is a
bigger liability than losing the local copy.

Errors from the underlying Firestore client are translated into
``IdentityRepositoryError`` so callers never need to know about
``google.api_core`` specifics.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.constants import ErrorCode, FirestoreCollection
from app.core.exceptions import NovaBanqError
from app.infra.firestore import document

logger = logging.getLogger(__name__)


class IdentityRepositoryError(NovaBanqError):
    """Raised when the identity repository cannot complete an operation.

    From the caller's perspective, a Firestore failure during identity
    verification is the same class of problem as the KYC provider being
    down: retry later.
    """

    status_code = 502
    code = ErrorCode.IDENTITY_PROVIDER_UNAVAILABLE
    message = "Identity verification storage is temporarily unavailable."


def upsert_verification(
    *,
    uid: str,
    status: str,
    provider: str,
    provider_reference: str | None,
    confidence: float | None,
    bvn_masked: str,
) -> None:
    """Write or replace the verification record for a user.

    Idempotent by design — the document id is the uid, so a repeated
    call overwrites the previous record. Called after every verification
    attempt, regardless of outcome, so the audit trail includes
    rejections and watchlist hits.

    Args:
        uid: Firebase uid of the user the verification belongs to.
        status: One of ``VERIFIED``, ``REJECTED``, ``WATCHLISTED``,
            ``NOT_FOUND``. Passed as a plain string to avoid coupling
            this module to the provider-layer enum.
        provider: Short label of the adapter that produced this result
            (e.g. ``"african_kyc"``, ``"mock"``).
        provider_reference: The provider's own reference id, if any.
        confidence: Face match confidence between 0.0 and 1.0, or None.
        bvn_masked: The BVN with all but the last four digits masked.

    Raises:
        IdentityRepositoryError: On any Firestore write failure.
    """
    payload: dict[str, Any] = {
        "uid": uid,
        "status": status,
        "provider": provider,
        "provider_reference": provider_reference,
        "confidence": confidence,
        "bvn_masked": bvn_masked,
        "verified_at": SERVER_TIMESTAMP,
    }

    try:
        document(FirestoreCollection.IDENTITY_VERIFICATIONS, uid).set(payload)
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception(
            "Failed to write identity verification for uid=%s.", uid
        )
        raise IdentityRepositoryError() from exc

    logger.info(
        "Recorded identity verification for uid=%s status=%s provider=%s.",
        uid,
        status,
        provider,
    )


def get_verification(uid: str) -> dict[str, Any] | None:
    """Return the verification record for a uid, or None if absent.

    Absence is a normal state — a user who has never attempted
    verification has no record, and that is not an error.

    Raises:
        IdentityRepositoryError: On any Firestore read failure.
    """
    try:
        snapshot = document(
            FirestoreCollection.IDENTITY_VERIFICATIONS, uid
        ).get()
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception(
            "Failed to read identity verification for uid=%s.", uid
        )
        raise IdentityRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    data.setdefault("uid", uid)
    return data


def is_verified(uid: str) -> bool:
    """Return True only if a VERIFIED record exists for this uid.

    A ``REJECTED``, ``WATCHLISTED``, or ``NOT_FOUND`` record does **not**
    count as verified. This is the single check the rest of the
    codebase should use to gate on identity status.

    Raises:
        IdentityRepositoryError: On any Firestore read failure.
    """
    record = get_verification(uid)
    if record is None:
        return False
    return record.get("status") == "VERIFIED"


def verification_timestamp(record: dict[str, Any]) -> datetime | None:
    """Return the ``verified_at`` field as a timezone-aware datetime.

    Firestore returns naive datetimes for stored timestamp fields.
    This helper normalizes to UTC so callers can compare against
    ``datetime.now(timezone.utc)`` without raising.

    Kept in the repository so the coercion lives next to the storage
    shape, and the service layer stays free of Firestore specifics.
    """
    value = record.get("verified_at")
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value