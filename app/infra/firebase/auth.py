"""Firebase Authentication integration.

This module is the only place in the codebase that talks directly to the
Firebase Authentication SDK. All other modules import from here.
"""

import logging
from typing import Any

from firebase_admin import auth as firebase_auth

from app.core.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)


def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return its decoded claims.

    Args:
        id_token: The raw Firebase ID token extracted from the
            ``Authorization: Bearer <token>`` header.

    Returns:
        The decoded token claims, guaranteed to contain a ``uid`` field.

    Raises:
        InvalidTokenError: If the token is malformed, expired, revoked,
            or belongs to a different Firebase project.
    """
    if not id_token or not id_token.strip():
        raise InvalidTokenError("The provided token is empty.")

    try:
        decoded = firebase_auth.verify_id_token(id_token, check_revoked=True)
    except firebase_auth.ExpiredIdTokenError as exc:
        logger.info("Rejected expired Firebase ID token.")
        raise InvalidTokenError("The provided token has expired.") from exc
    except firebase_auth.RevokedIdTokenError as exc:
        logger.warning("Rejected revoked Firebase ID token.")
        raise InvalidTokenError("The provided token has been revoked.") from exc
    except firebase_auth.InvalidIdTokenError as exc:
        logger.warning("Rejected invalid Firebase ID token.")
        raise InvalidTokenError("The provided token is invalid.") from exc
    except Exception as exc:  # noqa: BLE001 — final safety net around SDK
        logger.exception("Unexpected error while verifying Firebase ID token.")
        raise InvalidTokenError("The provided token could not be verified.") from exc

    uid = decoded.get("uid")
    if not uid:
        logger.warning("Firebase token verified but contained no uid claim.")
        raise InvalidTokenError("The provided token is missing a uid claim.")

    return decoded


def get_user_email(id_token: str) -> str | None:
    """Return the email claim from a verified token, if present."""
    decoded = verify_id_token(id_token)
    return decoded.get("email")


def revoke_user_tokens(uid: str) -> None:
    """Revoke all refresh tokens for a user.

    Useful for logout-everywhere flows and forced sign-outs after
    security-sensitive events.
    """
    firebase_auth.revoke_refresh_tokens(uid)
    logger.info("Revoked all refresh tokens for uid=%s.", uid)