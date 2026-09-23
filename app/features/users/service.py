"""User service.

Business logic for the user lifecycle:

    * Profile creation (gated on email verification unless the account
      was created via Google sign-in).
    * Profile retrieval, name corrections, and @tag assignment.
    * PIN set / verify / reset with a lockout policy.
    * Email, phone, and identity verification flags.

This layer orchestrates the users repository, the account_numbers
service, and the tags service. It contains no HTTP and no direct
Firestore calls.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.constants import (
    COUNTRY_TAG_SUFFIX,
    PIN_LOCKOUT_MINUTES,
    PIN_MAX_ATTEMPTS,
    TAG_SUFFIX_SEPARATOR,
    Country,
    Currency,
    ErrorCode,
    OtpPurpose,
)
from app.core.exceptions import (
    NovaBanqError,
    TagTakenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.security import hash_pin, verify_pin
from app.features.account_numbers.service import generate_and_reserve
from app.features.otp import service as otp_service
from app.features.tags import service as tags_service
from app.features.users import repository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class PinAlreadySetError(NovaBanqError):
    status_code = 409
    code = ErrorCode.PIN_ALREADY_SET
    message = "A PIN is already set for this account."


class PinNotSetError(NovaBanqError):
    status_code = 409
    code = ErrorCode.PIN_INVALID
    message = "No PIN has been set for this account."


class PinInvalidError(NovaBanqError):
    status_code = 422
    code = ErrorCode.PIN_INVALID
    message = "The PIN you entered is incorrect."


class PinLockedError(NovaBanqError):
    status_code = 429
    code = ErrorCode.PIN_LOCKED
    message = "Too many incorrect attempts. The PIN is temporarily locked."


class PhoneMismatchError(NovaBanqError):
    status_code = 422
    code = ErrorCode.PHONE_MISMATCH
    message = "The verified phone number does not match this account."


class EmailNotVerifiedError(NovaBanqError):
    status_code = 403
    code = ErrorCode.EMAIL_NOT_VERIFIED
    message = "Your email must be verified before creating a profile."


class IdentityAlreadyVerifiedError(NovaBanqError):
    status_code = 409
    code = ErrorCode.IDENTITY_ALREADY_VERIFIED
    message = "Identity is already verified. Names cannot be changed."


class UnsupportedCountryError(NovaBanqError):
    status_code = 422
    code = ErrorCode.VALIDATION_ERROR
    message = "This country is not currently supported."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Country → default settlement currency. Extend as new corridors launch.
_DEFAULT_CURRENCY_BY_COUNTRY: dict[str, Currency] = {
    Country.NIGERIA: Currency.NGN,
    Country.GHANA: Currency.GHS,
    Country.KENYA: Currency.KES,
    Country.SENEGAL: Currency.XOF,
    Country.IVORY_COAST: Currency.XOF,
    Country.SOUTH_AFRICA: Currency.ZAR,
}

_GOOGLE_SIGN_IN_PROVIDER = "google.com"


def _default_currency(country: Country) -> Currency:
    """Return the default settlement currency for a country."""
    currency = _DEFAULT_CURRENCY_BY_COUNTRY.get(country)
    if currency is None:
        raise UnsupportedCountryError()
    return currency


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _to_aware(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive Firestore datetime to UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_google_sign_in(claims: dict[str, Any]) -> bool:
    """Return True if the token was issued for a Google sign-in."""
    return (
        claims.get("firebase", {}).get("sign_in_provider")
        == _GOOGLE_SIGN_IN_PROVIDER
    )


def _has_verified_email_otp(uid: str) -> bool:
    """Return True if a durable email-verified marker exists for this uid.

    Delegated to the OTP service so the marker id format lives in
    exactly one place.
    """
    return otp_service.has_verified_marker(uid, OtpPurpose.EMAIL_VERIFICATION)


def _build_full_tag(base_tag: str, country: str) -> str:
    """Append the country suffix to a base tag.

    Args:
        base_tag: The tag name without any suffix (e.g. "david323").
        country: Two-letter ISO country code from the user's profile.

    Returns:
        The full tag with suffix (e.g. "david323.ng").

    Raises:
        UnsupportedCountryError: If the country has no configured suffix.
    """
    suffix = COUNTRY_TAG_SUFFIX.get(country)
    if suffix is None:
        raise UnsupportedCountryError()
    return f"{base_tag}{TAG_SUFFIX_SEPARATOR}{suffix}"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def create_profile(
    uid: str,
    *,
    first_name: str,
    middle_name: str,
    last_name: str,
    country: Country,
    phone: str,
    email: str | None,
    claims: dict[str, Any],
) -> dict[str, Any]:
    """Create a NovaBanq profile for a newly authenticated user.

    Raises:
        UserAlreadyExistsError: If a profile already exists.
        EmailNotVerifiedError: If the account is not Google and no
            verified email marker exists for this uid.
    """
    if repository.exists(uid):
        raise UserAlreadyExistsError()

    email_verified = _is_google_sign_in(claims)
    if not email_verified:
        email_verified = _has_verified_email_otp(uid)
        if not email_verified:
            raise EmailNotVerifiedError()

    currency = _default_currency(country)
    account_number = generate_and_reserve(uid, country)

    repository.create(
        uid,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        tag=None,
        country=country,
        currency=currency,
        phone=phone,
        email=email,
        account_number=account_number,
        email_verified=email_verified,
    )

    profile = repository.get_by_uid(uid)
    if profile is None:
        raise RuntimeError(f"User profile not found after creation for uid={uid}.")

    profile["uid"] = uid
    logger.info(
        "Profile created for uid=%s country=%s email_verified=%s.",
        uid,
        country,
        email_verified,
    )
    return profile


def get_profile(uid: str) -> dict[str, Any]:
    """Return the user's profile.

    Raises:
        UserNotFoundError: If no profile exists for the uid.
    """
    profile = repository.get_by_uid(uid)
    if profile is None:
        raise UserNotFoundError()
    profile["uid"] = uid
    return profile


def update_names(
    uid: str,
    *,
    first_name: str,
    middle_name: str,
    last_name: str,
) -> dict[str, Any]:
    """Replace the user's name fields.

    Names must be locked once identity verification succeeds, because
    the identity provider matched them against the government ID.

    Raises:
        UserNotFoundError: If no profile exists.
        IdentityAlreadyVerifiedError: If the user already passed identity
            verification.
    """
    profile = get_profile(uid)

    if profile.get("identity_verified"):
        raise IdentityAlreadyVerifiedError()

    repository.update_names(
        uid,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
    )

    profile["first_name"] = first_name
    profile["middle_name"] = middle_name
    profile["last_name"] = last_name
    logger.info("Names updated for uid=%s.", uid)
    return profile


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------

def check_tag_available(uid: str, base_tag: str) -> dict[str, Any]:
    """Check whether a base tag is available for the current user.

    The suffix is derived from the user's profile country, so the check
    is scoped correctly (e.g. "david323.ng" for a Nigerian user). This
    is a read-only operation; the tag is not reserved. A subsequent
    claim may still fail if another user wins the race.

    Args:
        uid: Firebase uid of the caller.
        base_tag: The tag name without any suffix (already normalized
            by the request validator).

    Returns:
        A dict with the full tag and an availability boolean.

    Raises:
        UserNotFoundError: If the caller has no profile.
    """
    profile = get_profile(uid)
    full_tag = _build_full_tag(base_tag, profile["country"])

    available = tags_service.is_available(full_tag)
    return {"tag": full_tag, "available": available}


def claim_tag(uid: str, base_tag: str) -> dict[str, Any]:
    """Assign a @tag to the user after verifying uniqueness.

    The country suffix is appended from the user's profile — never from
    user input — so a Nigerian user cannot claim a ".gh" tag.

    Raises:
        UserNotFoundError: If the caller has no profile.
        TagTakenError: If the full tag is already claimed by another user.
    """
    profile = get_profile(uid)
    full_tag = _build_full_tag(base_tag, profile["country"])

    if profile.get("tag") == full_tag:
        return profile

    tags_service.reserve(full_tag, uid)
    repository.update_tag(uid, full_tag)

    profile["tag"] = full_tag
    logger.info("Tag '@%s' claimed by uid=%s.", full_tag, uid)
    return profile


# ---------------------------------------------------------------------------
# Email / phone / identity verification
# ---------------------------------------------------------------------------

def mark_email_verified(uid: str) -> None:
    """Flag the user's email as verified."""
    repository.mark_email_verified(uid)


def set_phone_verified(uid: str, phone_number: str) -> None:
    """Mark the user's phone as verified after Firebase Phone Auth.

    Raises:
        UserNotFoundError: If the user has no profile.
        PhoneMismatchError: If the verified phone differs from the
            stored phone.
    """
    profile = get_profile(uid)
    stored = profile.get("phone")

    if stored and stored != phone_number:
        logger.warning(
            "Phone verification mismatch for uid=%s: token=%s stored=%s.",
            uid,
            phone_number,
            stored,
        )
        raise PhoneMismatchError()

    repository.mark_phone_verified(uid, phone_number)


def mark_identity_verified(uid: str) -> None:
    """Flag the user as having completed identity verification.

    Called by the identity feature after both BVN/national ID and face
    verification succeed. Once set, the name fields are locked.
    """
    repository.mark_identity_verified(uid)


# ---------------------------------------------------------------------------
# PIN
# ---------------------------------------------------------------------------

def set_pin(uid: str, pin: str) -> None:
    """Set the user's PIN.

    Raises:
        UserNotFoundError: If no profile exists for the uid.
        PinAlreadySetError: If a PIN is already set.
    """
    profile = get_profile(uid)
    if profile.get("pin_hash"):
        raise PinAlreadySetError()

    repository.set_pin_hash(uid, hash_pin(pin))
    logger.info("PIN set for uid=%s.", uid)


def verify_pin_for_uid(uid: str, pin: str) -> None:
    """Verify the user's PIN, enforcing the lockout policy.

    Raises:
        UserNotFoundError: If no profile exists for the uid.
        PinNotSetError: If the user has not set a PIN.
        PinLockedError: If the PIN is currently locked.
        PinInvalidError: If the PIN does not match.
    """
    profile = get_profile(uid)

    pin_hash = profile.get("pin_hash")
    if not pin_hash:
        raise PinNotSetError()

    locked_until = _to_aware(profile.get("pin_locked_until"))
    now = _utc_now()
    if locked_until is not None and now < locked_until:
        remaining = int((locked_until - now).total_seconds())
        raise PinLockedError(
            f"Too many incorrect attempts. Try again in {remaining} second(s)."
        )

    if not verify_pin(pin, pin_hash):
        attempts = int(profile.get("pin_attempts", 0)) + 1
        new_lock = (
            now + timedelta(minutes=PIN_LOCKOUT_MINUTES)
            if attempts >= PIN_MAX_ATTEMPTS
            else None
        )
        repository.record_failed_pin_attempt(
            uid,
            attempts=attempts,
            locked_until=new_lock,
        )
        raise PinInvalidError()

    repository.reset_pin_attempts(uid)
    logger.info("PIN verified for uid=%s.", uid)


def reset_pin(uid: str, token_phone_number: str | None) -> None:
    """Clear the user's PIN after identity is re-confirmed via phone.

    Raises:
        UserNotFoundError: If no profile exists for the uid.
        PhoneMismatchError: If the token has no phone claim, or the
            claim does not match the stored phone.
    """
    profile = get_profile(uid)
    stored = profile.get("phone")

    if not token_phone_number:
        raise PhoneMismatchError()
    if stored and stored != token_phone_number:
        raise PhoneMismatchError()

    repository.clear_pin(uid)
    logger.info("PIN reset completed for uid=%s.", uid)