"""OTP repository.

Data access layer for the ``otp_codes`` Firestore collection. Each
document represents a single active OTP for a given uid and purpose
(e.g. "email_verification"). Only one active OTP exists per
uid/purpose pair — issuing a new one overwrites the previous.

This module contains no business logic. It reads and writes documents.
Generation, hashing, expiry, and rate-limiting decisions belong in the
service layer.
"""

import logging
from typing import Any

from app.core.constants import FirestoreCollection
from app.infra.firestore import document

logger = logging.getLogger(__name__)


def _doc_id(uid: str, purpose: str) -> str:
    """Build the composite document id for a uid/purpose pair.

    Using a composite id enforces at the database level that only one
    active OTP exists per uid and purpose: writing a new code for the
    same pair overwrites the previous document, so there is never a
    stale code lying around to be guessed.
    """
    return f"{uid}_{purpose}"


def get(uid: str, purpose: str) -> dict[str, Any] | None:
    """Return the active OTP document for a uid/purpose pair.

    Args:
        uid: Firebase uid the OTP was issued to.
        purpose: The OTP purpose, e.g. "email_verification".

    Returns:
        The OTP document data, or ``None`` if no OTP is active.
    """
    snapshot = document(FirestoreCollection.OTP_CODES, _doc_id(uid, purpose)).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def upsert(
    uid: str,
    purpose: str,
    *,
    code_hash: str,
    expires_at: Any,
    sent_at: Any,
) -> None:
    """Create or replace the active OTP document for a uid/purpose pair.

    Args:
        uid: Firebase uid the OTP is being issued to.
        purpose: The OTP purpose.
        code_hash: SHA-256 hex digest of the plaintext code.
        expires_at: UTC datetime when the code stops being valid.
        sent_at: UTC datetime when the code was delivered.
    """
    document(FirestoreCollection.OTP_CODES, _doc_id(uid, purpose)).set(
        {
            "uid": uid,
            "purpose": purpose,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "sent_at": sent_at,
            "attempts": 0,
        }
    )
    logger.info("Upserted OTP for uid=%s purpose=%s.", uid, purpose)


def increment_attempts(uid: str, purpose: str, current: int) -> None:
    """Record one verification attempt against the active OTP.

    Firestore's ``Increment`` transform would be ideal here, but the
    service already holds the current value from the read it performs
    before verification. Passing the value in keeps the write explicit
    and avoids an extra round-trip.

    Args:
        uid: Firebase uid the OTP was issued to.
        purpose: The OTP purpose.
        current: The attempt count before this increment.
    """
    document(FirestoreCollection.OTP_CODES, _doc_id(uid, purpose)).update(
        {"attempts": current + 1}
    )


def delete(uid: str, purpose: str) -> None:
    """Remove the active OTP document after successful verification.

    Deleting rather than flagging as consumed ensures that a captured
    code cannot be replayed once it has been used.
    """
    document(FirestoreCollection.OTP_CODES, _doc_id(uid, purpose)).delete()
    logger.info("Deleted OTP for uid=%s purpose=%s.", uid, purpose)