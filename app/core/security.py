"""Authentication and credential-security helpers.

This module exposes:

    * ``get_current_uid`` — verifies the Firebase ID token and returns
      the authenticated uid.
    * ``get_current_claims`` — returns the full decoded token so routes
      can inspect claims such as ``sign_in_provider`` and
      ``phone_number``.
    * ``get_current_user`` / ``require_user`` — load the caller's
      Firestore profile.
    * ``hash_pin`` / ``verify_pin`` — bcrypt helpers for PIN storage.

Concurrency note:
    ``verify_id_token`` and Firestore reads are synchronous, blocking
    I/O. FastAPI runs plain ``def`` dependencies in its threadpool, so
    these are declared as ``def`` — not ``async def`` — to avoid
    stalling the event loop on every protected request.
"""

import logging
from typing import Annotated, Any

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.constants import FirestoreCollection
from app.core.exceptions import MissingTokenError, UserNotFoundError
from app.infra.firebase.auth import verify_id_token
from app.infra.firestore import document

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

def get_current_claims(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> dict[str, Any]:
    """Verify the Firebase ID token and return its decoded claims.

    Use this dependency when a route needs more than the uid — for
    example to check ``firebase.sign_in_provider`` or ``phone_number``.
    """
    if credentials is None or not credentials.credentials.strip():
        logger.warning("Authentication failed: missing or empty bearer token.")
        raise MissingTokenError()

    return verify_id_token(credentials.credentials)


def get_current_uid(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
) -> str:
    """Return the authenticated uid extracted from the verified token."""
    uid = claims.get("uid")
    if not uid:
        logger.warning("Authentication failed: verified token has no uid claim.")
        raise MissingTokenError()
    return uid


def get_current_user(
    uid: Annotated[str, Depends(get_current_uid)],
) -> dict[str, Any]:
    """Load the Firestore profile document for the authenticated user.

    Raises:
        UserNotFoundError: If the user has authenticated with Firebase
            but has not yet completed NovaBanq profile creation.
    """
    snapshot = document(FirestoreCollection.USERS, uid).get()
    if not snapshot.exists:
        raise UserNotFoundError()

    data = snapshot.to_dict() or {}
    data["uid"] = uid
    return data


def require_user(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Return the authenticated user, ensuring onboarding is complete.

    ``account_number`` is generated during profile creation and never
    removed, so its presence is a reliable signal that onboarding
    completed.
    """
    if not user.get("account_number"):
        raise UserNotFoundError()
    return user


CurrentClaims = Annotated[dict[str, Any], Depends(get_current_claims)]
CurrentUid = Annotated[str, Depends(get_current_uid)]
CurrentUser = Annotated[dict[str, Any], Depends(require_user)]


# ---------------------------------------------------------------------------
# PIN hashing
# ---------------------------------------------------------------------------

_BCRYPT_ROUNDS = 12


def hash_pin(pin: str) -> str:
    """Hash a PIN with bcrypt.

    The returned string includes the algorithm identifier, cost factor,
    and salt, so ``verify_pin`` needs no external state to validate.
    """
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(pin.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Check a plaintext PIN against a stored bcrypt hash.

    Returns False — never raises — for a malformed hash, so a corrupt
    value is treated as "no match" rather than crashing the request.
    """
    if not pin_hash:
        return False
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except ValueError:
        logger.warning("Stored PIN hash is malformed; treating as no match.")
        return False