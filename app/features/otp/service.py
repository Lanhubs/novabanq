"""OTP service.

Business logic for one-time password issuance and verification.

Responsibilities:
    * Generate cryptographically secure codes.
    * Hash codes before storage — plaintext is never persisted.
    * Enforce expiry, max attempts, and resend cooldown.
    * Deliver codes via the email client for email-purpose OTPs.
    * On successful verification, write a durable marker so downstream
      flows (profile creation) can prove email ownership without
      depending on the transient OTP document.

The phone-purpose OTP path is intentionally absent: phone verification
is handled entirely by Firebase Phone Auth on the client. This service
covers email verification only.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.constants import (
    OTP_CODE_LENGTH,
    OTP_EXPIRY_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
    ErrorCode,
    FirestoreCollection,
    OtpPurpose,
)
from app.core.exceptions import NovaBanqError
from app.features.otp import repository
from app.infra.email.client import send_email
from app.infra.email.templates import render_otp_email
from app.infra.firestore import document

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class OtpInvalidError(NovaBanqError):
    status_code = 422
    code = ErrorCode.OTP_INVALID
    message = "The verification code is incorrect."


class OtpExpiredError(NovaBanqError):
    status_code = 422
    code = ErrorCode.OTP_EXPIRED
    message = "The verification code has expired. Please request a new one."


class OtpTooManyAttemptsError(NovaBanqError):
    status_code = 429
    code = ErrorCode.OTP_TOO_MANY_ATTEMPTS
    message = "Too many incorrect attempts. Please request a new code."


class OtpResendTooSoonError(NovaBanqError):
    status_code = 429
    code = ErrorCode.OTP_RESEND_TOO_SOON
    message = "Please wait before requesting another code."


class OtpNotFoundError(NovaBanqError):
    status_code = 422
    code = ErrorCode.OTP_INVALID
    message = "No active verification code was found. Please request a new one."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _verified_marker_id(uid: str, purpose: OtpPurpose) -> str:
    """Return the Firestore document id for a durable verified marker."""
    return f"{uid}_{purpose}_verified"


def _generate_code() -> str:
    """Generate a numeric OTP code using a cryptographic source."""
    upper_bound = 10 ** OTP_CODE_LENGTH
    return str(secrets.randbelow(upper_bound)).zfill(OTP_CODE_LENGTH)


def _hash_code(code: str) -> str:
    """Return the SHA-256 hex digest of a code."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _to_aware(value: datetime) -> datetime:
    """Ensure a datetime read from Firestore is timezone-aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _write_verified_marker(uid: str, purpose: OtpPurpose) -> None:
    """Write a durable record that a uid has verified this purpose.

    The OTP document itself is deleted on success so a captured code
    cannot be replayed. Downstream flows (profile creation) still need
    to prove the verification happened. This marker provides that
    durable signal.

    The marker is intentionally minimal — uid, purpose, and timestamp.
    It contains no code, no hash, and no PII.
    """
    document(
        FirestoreCollection.OTP_CODES,
        _verified_marker_id(uid, purpose),
    ).set(
        {
            "uid": uid,
            "purpose": purpose,
            "verified_at": SERVER_TIMESTAMP,
        }
    )
    logger.info(
        "Wrote durable verified marker for uid=%s purpose=%s.",
        uid,
        purpose,
    )


def has_verified_marker(uid: str, purpose: OtpPurpose) -> bool:
    """Return True if a durable verified marker exists for this uid.

    Callers use this to prove a purpose has been completed, e.g. to
    gate profile creation on email verification.
    """
    snapshot = document(
        FirestoreCollection.OTP_CODES,
        _verified_marker_id(uid, purpose),
    ).get()
    return snapshot.exists


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def issue_email_verification(uid: str, email: str) -> None:
    """Issue an email verification OTP and send it to the user.

    Raises:
        OtpResendTooSoonError: If a code was sent within the cooldown window.
        EmailDeliveryError: If the email cannot be delivered.
    """
    purpose = OtpPurpose.EMAIL_VERIFICATION
    now = _utc_now()

    existing = repository.get(uid, purpose)
    if existing is not None:
        sent_at = _to_aware(existing["sent_at"])
        elapsed = (now - sent_at).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise OtpResendTooSoonError(
                f"Please wait {wait} more second(s) before requesting another code."
            )

    code = _generate_code()
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

    repository.upsert(
        uid,
        purpose,
        code_hash=_hash_code(code),
        expires_at=expires_at,
        sent_at=now,
    )

    content = render_otp_email(
        code=code,
        expires_in_minutes=OTP_EXPIRY_MINUTES,
    )

    send_email(
        to_email=email,
        subject=content.subject,
        html_content=content.html,
        text_content=content.text,
        tags=content.tags,
    )

    logger.info("Issued email verification OTP for uid=%s.", uid)


def verify_email_verification(uid: str, code: str) -> None:
    """Verify an email verification OTP.

    On success the OTP document is deleted (no replay) and a durable
    verified marker is written so profile creation can gate on the
    result. On failure the attempt counter is incremented.

    Raises:
        OtpNotFoundError: If no active code exists for this uid.
        OtpExpiredError: If the code's expiry has passed.
        OtpTooManyAttemptsError: If the attempt limit has been reached.
        OtpInvalidError: If the code does not match.
    """
    purpose = OtpPurpose.EMAIL_VERIFICATION
    record = repository.get(uid, purpose)

    if record is None:
        raise OtpNotFoundError()

    attempts = int(record.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        raise OtpTooManyAttemptsError()

    expires_at = _to_aware(record["expires_at"])
    if _utc_now() > expires_at:
        repository.delete(uid, purpose)
        raise OtpExpiredError()

    if _hash_code(code) != record["code_hash"]:
        repository.increment_attempts(uid, purpose, attempts)
        raise OtpInvalidError()

    repository.delete(uid, purpose)
    _write_verified_marker(uid, purpose)
    logger.info("Verified email verification OTP for uid=%s.", uid)