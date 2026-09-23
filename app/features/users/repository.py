"""User repository.

Data access layer for the ``users`` Firestore collection. Each document
is keyed by the Firebase uid, so lookups by uid are O(1).

This module contains no business logic — no validation, no
orchestration, no side effects beyond the Firestore write. Those
belong in the service layer.

Fields on a user document:
    first_name           str           required, from signup
    middle_name          str           required, from signup
    last_name            str           required, from signup
    tag                  str | None    @tag without the leading '@'
    country              str           two-letter ISO code
    currency             str           default settlement currency
    phone                str           E.164 format
    email                str | None
    email_verified       bool          flipped by the OTP flow
    phone_verified       bool          flipped by the phone verify flow
    account_number       str           NB + country + 8 digits
    pin_hash             str | None    bcrypt hash, set when PIN created
    pin_attempts         int           failed PIN attempts since last success
    pin_locked_until     datetime | None
    identity_verified    bool          flipped by the identity module
    created_at           datetime      server timestamp
"""

import logging
from datetime import datetime
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.constants import FirestoreCollection
from app.infra.firestore import document

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def get_by_uid(uid: str) -> dict[str, Any] | None:
    """Return the user document for the given uid, or None if absent."""
    snapshot = document(FirestoreCollection.USERS, uid).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def exists(uid: str) -> bool:
    """Return True if a user document exists for the given uid."""
    return get_by_uid(uid) is not None


def create(
    uid: str,
    *,
    first_name: str,
    middle_name: str,
    last_name: str,
    tag: str | None,
    country: str,
    currency: str,
    phone: str,
    email: str | None,
    account_number: str,
    email_verified: bool,
) -> None:
    """Create a user document with the given fields.

    Args:
        uid: Firebase uid, used as the document id.
        first_name: Given name as entered by the user.
        middle_name: Middle name as entered by the user.
        last_name: Family name as entered by the user.
        tag: The user's @tag without the leading '@', or None if unclaimed.
        country: Two-letter ISO country code.
        currency: Default settlement currency code.
        phone: Phone number in E.164 format.
        email: Email address, or None if unavailable.
        account_number: The reserved NovaBanq account number.
        email_verified: Whether the email has already been verified
            (true for Google sign-in, false for email/password).
    """
    document(FirestoreCollection.USERS, uid).set(
        {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "tag": tag,
            "country": country,
            "currency": currency,
            "phone": phone,
            "email": email,
            "email_verified": email_verified,
            "phone_verified": False,
            "account_number": account_number,
            "pin_hash": None,
            "pin_attempts": 0,
            "pin_locked_until": None,
            "identity_verified": False,
            "created_at": SERVER_TIMESTAMP,
        }
    )
    logger.info(
        "Created user profile uid=%s country=%s email_verified=%s.",
        uid,
        country,
        email_verified,
    )


def update_names(
    uid: str,
    *,
    first_name: str,
    middle_name: str,
    last_name: str,
) -> None:
    """Replace the user's name fields.

    Intended for corrections before identity verification. Once
    ``identity_verified`` is true, the names must match the government
    ID and should not be changed without re-verification.
    """
    document(FirestoreCollection.USERS, uid).update(
        {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
        }
    )
    logger.info("Updated names for uid=%s.", uid)


def update_tag(uid: str, tag: str) -> None:
    """Set the user's @tag."""
    document(FirestoreCollection.USERS, uid).update({"tag": tag})
    logger.info("Updated tag for uid=%s to '@%s'.", uid, tag)


def update_email(uid: str, email: str) -> None:
    """Set the user's email address."""
    document(FirestoreCollection.USERS, uid).update({"email": email})


def mark_email_verified(uid: str) -> None:
    """Flag the user's email as verified."""
    document(FirestoreCollection.USERS, uid).update({"email_verified": True})
    logger.info("Marked email verified for uid=%s.", uid)


def mark_phone_verified(uid: str, phone: str) -> None:
    """Flag the user's phone as verified and store the confirmed number."""
    document(FirestoreCollection.USERS, uid).update(
        {
            "phone": phone,
            "phone_verified": True,
        }
    )
    logger.info("Marked phone verified for uid=%s.", uid)


def mark_identity_verified(uid: str) -> None:
    """Flag the user as having completed identity verification."""
    document(FirestoreCollection.USERS, uid).update({"identity_verified": True})
    logger.info("Marked identity verified for uid=%s.", uid)


# ---------------------------------------------------------------------------
# PIN state
# ---------------------------------------------------------------------------

def set_pin_hash(uid: str, pin_hash: str) -> None:
    """Store the user's hashed PIN and reset attempt/lock state."""
    document(FirestoreCollection.USERS, uid).update(
        {
            "pin_hash": pin_hash,
            "pin_attempts": 0,
            "pin_locked_until": None,
        }
    )
    logger.info("Set PIN for uid=%s.", uid)


def record_failed_pin_attempt(
    uid: str,
    *,
    attempts: int,
    locked_until: datetime | None,
) -> None:
    """Update the failed-attempt counter and, if applicable, the lockout.

    Args:
        uid: Firebase uid.
        attempts: The new attempt count after this failure.
        locked_until: If the lockout was triggered by this failure, the
            UTC datetime until which the PIN is locked. Otherwise None.
    """
    document(FirestoreCollection.USERS, uid).update(
        {
            "pin_attempts": attempts,
            "pin_locked_until": locked_until,
        }
    )
    if locked_until:
        logger.warning(
            "PIN locked for uid=%s until %s after %d failed attempts.",
            uid,
            locked_until.isoformat(),
            attempts,
        )


def reset_pin_attempts(uid: str) -> None:
    """Clear the failed-attempt counter and lockout after a success."""
    document(FirestoreCollection.USERS, uid).update(
        {
            "pin_attempts": 0,
            "pin_locked_until": None,
        }
    )


def clear_pin(uid: str) -> None:
    """Remove the user's PIN and reset all PIN state.

    Used by the forgot-PIN flow after identity has been re-confirmed via
    Firebase Phone Auth. After this call the user is back in the
    "no PIN set" state and may call ``set_pin`` again.
    """
    document(FirestoreCollection.USERS, uid).update(
        {
            "pin_hash": None,
            "pin_attempts": 0,
            "pin_locked_until": None,
        }
    )
    logger.info("Cleared PIN state for uid=%s.", uid)