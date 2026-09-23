"""OTP endpoints.

HTTP surface for one-time password issuance and verification. Every
route is authenticated — the uid always comes from the verified
Firebase token, never from the request body.

The email address the OTP is sent to is resolved from the authenticated
user's Firebase record, not from the request. This closes the obvious
attack of "send an OTP to any address I choose."
"""

import logging
from typing import Any

from fastapi import APIRouter, status
from firebase_admin import auth as firebase_auth

from app.core.constants import OTP_EXPIRY_MINUTES, OTP_RESEND_COOLDOWN_SECONDS
from app.core.exceptions import NovaBanqError
from app.core.security import CurrentUid
from app.features.otp import service
from app.features.otp.schemas import (
    OtpIssuedResponse,
    SendEmailOtpRequest,
    VerifyEmailOtpRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class UserEmailMissingError(NovaBanqError):
    """Raised when the authenticated Firebase user has no email address."""

    status_code = 422
    message = "No email address is associated with this account."


def _ok(data: Any) -> dict[str, Any]:
    """Wrap a response payload in the standard success envelope."""
    return {"success": True, "data": data, "error": None}


def _resolve_user_email(uid: str) -> str:
    """Return the verified email address for a Firebase uid.

    The email is read from Firebase, not from the request body, so a
    caller cannot redirect an OTP to an address they control.

    Raises:
        UserEmailMissingError: If the Firebase user record has no email.
    """
    user_record = firebase_auth.get_user(uid)
    if not user_record.email:
        raise UserEmailMissingError()
    return user_record.email


@router.post(
    "/email/send",
    status_code=status.HTTP_200_OK,
    summary="Send an email verification OTP",
    description=(
        "Issues a one-time verification code and delivers it to the "
        "email address on the authenticated user's Firebase record. "
        "Enforces a resend cooldown to prevent abuse."
    ),
)
async def send_email_otp(
    uid: CurrentUid,
    _payload: SendEmailOtpRequest,
) -> dict[str, Any]:
    email = _resolve_user_email(uid)
    service.issue_email_verification(uid, email)

    return _ok(
        OtpIssuedResponse(
            sent=True,
            expires_in_seconds=OTP_EXPIRY_MINUTES * 60,
            resend_available_in_seconds=OTP_RESEND_COOLDOWN_SECONDS,
        ).model_dump()
    )


@router.post(
    "/email/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify an email OTP",
    description=(
        "Validates the code the user received. On success the code is "
        "consumed and cannot be reused."
    ),
)
async def verify_email_otp(
    uid: CurrentUid,
    payload: VerifyEmailOtpRequest,
) -> dict[str, Any]:
    service.verify_email_verification(uid, payload.code)

    return _ok({"verified": True})