"""Identity verification service.

Orchestrates the verification flow:

    1. Loads the user profile and enforces business rules.
    2. Selects the correct provider adapter (factory) and calls it with
       a signed Cloudinary URL.
    3. Schedules Cloudinary cleanup once the provider has seen the
       image — this still happens even if persisting the outcome or
       flipping the profile flag afterward fails.
    4. Persists the normalized outcome.
    5. Flips ``identity_verified`` on the profile when verification passes.

This layer contains no HTTP and no direct Firestore or Cloudinary SDK
calls. Every external interaction goes through a repository or an
infrastructure module.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.exceptions import NovaBanqError, UserNotFoundError
from app.features.identity import repository
from app.features.users import service as users_service
from app.infra.cloudinary_client import (
    CloudinaryClientError,
    build_authenticated_url,
    delete_asset,
)
from app.infra.identity.african_kyc import AfricanKYCProvider
from app.infra.identity.base import (
    IdentityProvider,
    IdentityProviderError,
    IdentityResult,
    VerificationStatus,
)
from app.infra.identity.mock import MockIdentityProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class IdentityAlreadyVerifiedError(NovaBanqError):
    """Raised when a user who has already passed verification tries again."""

    status_code = 409
    code = ErrorCode.IDENTITY_ALREADY_VERIFIED
    message = "Identity is already verified."


class IdentityUnavailableError(NovaBanqError):
    """Raised when the identity service cannot complete the request.

    Wraps every infrastructure failure — provider, repository, or
    image service — into a single retryable outcome. The client never
    sees which subsystem failed.
    """

    status_code = 502
    code = ErrorCode.IDENTITY_PROVIDER_UNAVAILABLE
    message = "Identity verification is temporarily unavailable."


class IdentityConfigurationError(NovaBanqError):
    """Raised when the identity provider is misconfigured.

    This is a deployment problem, not a client problem. It surfaces
    loudly in logs and returns a 500 so it is not mistaken for a
    transient outage.
    """

    status_code = 500
    code = ErrorCode.INTERNAL_ERROR
    message = "Identity verification is not configured."


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

_mock_provider = MockIdentityProvider()
_african_kyc_provider = AfricanKYCProvider()


def get_identity_provider() -> IdentityProvider:
    """Return the adapter selected by ``settings.kyc_provider``.

    Enforces the rule that the mock must never be reachable in
    production, regardless of how the environment variable is set.

    Raises:
        IdentityConfigurationError: If the provider name is unknown, or
            the mock was selected while ``APP_ENV=production``.
    """
    provider_name = settings.kyc_provider.strip().lower()

    if provider_name == "mock":
        if settings.is_production:
            logger.error(
                "KYC_PROVIDER=mock is not permitted in production."
            )
            raise IdentityConfigurationError(
                "The mock identity provider cannot be used in production."
            )
        return _mock_provider

    if provider_name == "african_kyc":
        return _african_kyc_provider

    logger.error("Unknown KYC_PROVIDER value: %r.", settings.kyc_provider)
    raise IdentityConfigurationError(
        f"Unknown identity provider: {settings.kyc_provider!r}."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_bvn_with_face(
    *,
    uid: str,
    bvn: str,
    cloudinary_public_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Verify a user's BVN against their uploaded selfie.

    The image is fetched from Cloudinary via a signed URL, passed to the
    identity provider, and the asset is scheduled for deletion as soon
    as the provider has seen it — independent of whether persisting the
    outcome or updating the profile afterward succeeds.

    Args:
        uid: Firebase uid of the caller.
        bvn: The 11-digit BVN to verify.
        cloudinary_public_id: Public id of the uploaded selfie. The
            request schema guarantees it is prefixed with the KYC folder.
        background_tasks: Scheduler for post-response cleanup.

    Returns:
        A dict matching ``VerifyIdentityResponse`` — status, confidence,
        masked BVN, and completion timestamp. The router wraps it in the
        standard response envelope.

    Raises:
        UserNotFoundError: No profile exists for this uid.
        IdentityAlreadyVerifiedError: The user has already passed.
        IdentityUnavailableError: Any infrastructure failure.
        IdentityConfigurationError: The provider is misconfigured.
    """
    # 1. Load profile — this raises UserNotFoundError if absent.
    profile = users_service.get_profile(uid)

    # 2. Block re-verification for already-verified users.
    if profile.get("identity_verified"):
        raise IdentityAlreadyVerifiedError()

    # 3. Build the signed Cloudinary URL and call the adapter.
    result = _run_verification(
        bvn=bvn,
        cloudinary_public_id=cloudinary_public_id,
    )

    # 4. Schedule cleanup now — the image has served its purpose the
    #    moment the provider has seen it. Scheduled here, before the
    #    persistence and profile-flag steps below, so a failure in
    #    either of those does not leave the asset orphaned in Cloudinary.
    background_tasks.add_task(delete_asset, cloudinary_public_id)

    # 5. Persist the outcome. Failure here is an outage — the user
    #    should retry, not see a rejection.
    try:
        repository.upsert_verification(
            uid=uid,
            status=result.status.value,
            provider=result.provider,
            provider_reference=result.provider_reference,
            confidence=_sanitize_confidence(result.confidence),
            bvn_masked=_mask_bvn(bvn),
        )
    except repository.IdentityRepositoryError as exc:
        raise IdentityUnavailableError() from exc

    # 6. Flip the profile flag only on a positive verdict.
    if result.status is VerificationStatus.VERIFIED:
        try:
            users_service.mark_identity_verified(uid)
        except Exception as exc:  # noqa: BLE001
            # The verification succeeded and was recorded; only the
            # profile flag failed. Log loudly — this needs manual repair
            # but must not deny the user a valid outcome.
            logger.exception(
                "Verified identity for uid=%s but failed to flag profile.",
                uid,
            )
            raise IdentityUnavailableError() from exc

    logger.info(
        "Identity verification for uid=%s completed with status=%s.",
        uid,
        result.status.value,
    )

    return {
        "status": result.status.value,
        "confidence": _sanitize_confidence(result.confidence),
        "bvn_masked": _mask_bvn(bvn),
        "verified_at": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_verification(
    *,
    bvn: str,
    cloudinary_public_id: str,
) -> IdentityResult:
    """Call the provider adapter with a signed image URL.

    Translates every infrastructure failure into ``IdentityUnavailable``
    so the caller's error handling stays uniform.

    Raises:
        IdentityUnavailableError: On any failure from Cloudinary, the
            provider, or the adapter's input validation contract.
        IdentityConfigurationError: If the provider is misconfigured.
    """
    # get_identity_provider() re-reads settings.kyc_provider on every
    # call rather than caching a choice made once at import time. That
    # means a misconfiguration — including an accidental
    # KYC_PROVIDER=mock in production — raises IdentityConfigurationError
    # on the request that actually needs a provider, and tests can swap
    # providers by overriding settings without restarting the process.
    provider = get_identity_provider()

    try:
        image_url = build_authenticated_url(cloudinary_public_id)
    except CloudinaryClientError as exc:
        raise IdentityUnavailableError() from exc

    try:
        return provider.verify_bvn_with_face(bvn=bvn, image=image_url)
    except IdentityProviderError as exc:
        logger.warning(
            "Identity provider failed for provider=%s: %s",
            provider.name,
            exc,
        )
        raise IdentityUnavailableError() from exc
    except ValueError as exc:
        # The request schema validates BVN and public ID, so a
        # ValueError here means the adapter rejected something the
        # schema allowed. That is an inconsistency in our own code, not
        # a client error.
        logger.exception("Adapter rejected a schema-valid request.")
        raise IdentityUnavailableError() from exc


def _sanitize_confidence(value: float | None) -> float | None:
    """Return a valid confidence in [0.0, 1.0], or None.

    Guards the response model against stale Firestore records written
    under a different scale. The adapter already validates at
    construction time; this is defense in depth at the read boundary.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0.0 <= value <= 1.0:
        logger.warning("Discarding out-of-range confidence value.")
        return None
    return float(value)


def _mask_bvn(bvn: str) -> str:
    """Return a BVN with all but the last four digits masked.

    Duplicated from the mock adapter by design: the service computes
    this for the response, and the adapter computes it for the stored
    record. Coupling them would mean a change to one silently affects
    the other.
    """
    if len(bvn) <= 4:
        return "*" * len(bvn)
    return "*" * (len(bvn) - 4) + bvn[-4:]