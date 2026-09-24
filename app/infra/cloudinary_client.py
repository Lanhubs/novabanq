"""Cloudinary client.

Thin wrapper around the Cloudinary SDK for two operations:

    1. Generate a short-lived signed payload the mobile client uses to
       upload an image directly to Cloudinary. The backend never handles
       image bytes.
    2. Delete an uploaded asset once it has served its purpose.

KYC selfies are uploaded with ``access_mode=authenticated`` — the asset
is not publicly readable by URL, and the client must present a signed
URL to view it. The mobile client uploads, the backend passes the asset
URL to the KYC provider, and the asset is deleted immediately after the
verification call returns.

Note: ``access_mode`` and Cloudinary's delivery ``type`` parameter are
two different access-control mechanisms. Assets here are uploaded with
the default delivery type (``upload``) plus ``access_mode=authenticated``,
so signed delivery URLs must also use ``type="upload"`` (the default) —
not ``type="authenticated"``, which is a separate, older mechanism for
assets actually stored under that distinct type.

The vendor's SDK is imported only in this file. Callers deal with plain
dicts and strings, never with the SDK's types.
"""

import logging
import time
from typing import Any

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from cloudinary.exceptions import Error as CloudinaryError

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.exceptions import NovaBanqError

logger = logging.getLogger(__name__)

# Cloudinary validates the upload timestamp against a rolling window
# server-side. The SDK does not accept a TTL parameter. This constant
# documents the effective window the mobile client has to complete the
# upload after receiving a signature.
_SIGNATURE_TTL_SECONDS = 600

# Default folder for KYC selfies. Avatars will use a different folder.
_KYC_FOLDER = "kyc-temp"

# Access mode: authenticated assets require a signed URL to view.
_AUTHENTICATED_ACCESS_MODE = "authenticated"


class CloudinaryClientError(NovaBanqError):
    """Raised when Cloudinary cannot complete an operation."""

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Image service is temporarily unavailable."


def _configure() -> None:
    """Apply Cloudinary credentials to the SDK once per process.

    The SDK stores configuration globally. Calling ``config`` repeatedly
    is idempotent but unnecessary, so we only do it when the SDK's
    current cloud name differs from what's required. This also makes
    the failure mode obvious if credentials are not set: the SDK raises
    on the first API call.

    Raises:
        RuntimeError: If any Cloudinary credential is missing.
    """
    cloud_name, api_key, api_secret = settings.require_cloudinary_config()

    if cloudinary.config().cloud_name != cloud_name:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )


def generate_upload_signature(
    *,
    folder: str = _KYC_FOLDER,
) -> dict[str, Any]:
    """Return a signed payload the client uses to upload directly.

    The client posts the returned values plus the image file to
    Cloudinary's upload endpoint. The signature proves the upload was
    authorized by this backend, and pins the upload's folder and
    access mode so a client cannot override them.

    Args:
        folder: Cloudinary folder the asset lands in. Defaults to the
            KYC staging folder. Future features pass their own.

    Returns:
        A dict with the fields the client must send:

            api_key      str   Cloudinary API key (public)
            cloud_name   str   Cloudinary cloud name (public)
            folder       str   Target folder
            timestamp    int   Unix seconds, signed
            access_mode  str   Always "authenticated", signed
            signature    str   HMAC-SHA1 of the signed parameters

    Raises:
        CloudinaryClientError: If Cloudinary cannot be configured.
    """
    try:
        _configure()
    except RuntimeError as exc:
        logger.error("Cloudinary credentials are not configured.")
        raise CloudinaryClientError("Image service is not configured.") from exc

    timestamp = int(time.time())

    # Parameters that must match exactly between signature generation
    # and the client's upload. Cloudinary hashes them in a specific
    # order — using the SDK's helper avoids any mismatch.
    signed_params: dict[str, Any] = {
        "folder": folder,
        "timestamp": timestamp,
        "access_mode": _AUTHENTICATED_ACCESS_MODE,
    }

    try:
        signature = cloudinary.utils.api_sign_request(
            signed_params,
            settings.cloudinary_api_secret or "",
        )
    except CloudinaryError as exc:
        logger.exception("Failed to generate Cloudinary upload signature.")
        raise CloudinaryClientError() from exc

    return {
        "api_key": settings.cloudinary_api_key,
        "cloud_name": settings.cloudinary_cloud_name,
        "folder": folder,
        "timestamp": timestamp,
        "access_mode": _AUTHENTICATED_ACCESS_MODE,
        "signature": signature,
    }


def delete_asset(public_id: str) -> bool:
    """Delete an asset from Cloudinary.

    Best-effort: a failure here is logged but not raised. The
    verification result matters more than cleanup success, and a
    failed delete is a retention concern, not a request failure.

    Args:
        public_id: The asset's public id, returned by Cloudinary on
            upload.

    Returns:
        True if the delete request was accepted by Cloudinary, False
        otherwise. Callers can log the outcome but should not gate on
        it.
    """
    if not public_id or not isinstance(public_id, str):
        logger.warning("delete_asset called with an empty public_id.")
        return False

    try:
        _configure()
        result = cloudinary.uploader.destroy(public_id)
    except (CloudinaryError, RuntimeError) as exc:
        logger.warning(
            "Failed to delete Cloudinary asset '%s': %s",
            public_id,
            exc,
        )
        return False

    status = result.get("result") if isinstance(result, dict) else None
    if status in ("ok", "not found"):
        # "not found" means the asset is already gone, which is fine.
        logger.info("Deleted Cloudinary asset '%s'.", public_id)
        return True

    logger.warning(
        "Cloudinary refused to delete '%s': %s",
        public_id,
        result,
    )
    return False


def build_authenticated_url(public_id: str) -> str:
    """Return a signed URL for an authenticated asset.

    Passed to the KYC provider so it can fetch the image. The URL is
    valid for the lifetime of the signed parameters only — the provider
    must fetch promptly.

    The asset was uploaded with ``access_mode=authenticated`` under the
    default delivery type (``upload``), so the signed URL must also use
    the default type. Passing ``type="authenticated"`` here would target
    Cloudinary's separate type-based access-control mechanism instead,
    and would not resolve to this asset.

    Args:
        public_id: The asset's public id.

    Returns:
        A fully signed HTTPS URL.

    Raises:
        CloudinaryClientError: If Cloudinary cannot be configured.
    """
    try:
        _configure()
    except RuntimeError as exc:
        logger.error("Cloudinary credentials are not configured.")
        raise CloudinaryClientError("Image service is not configured.") from exc

    try:
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            sign_url=True,
            secure=True,
        )
    except CloudinaryError as exc:
        logger.exception("Failed to build signed Cloudinary URL.")
        raise CloudinaryClientError() from exc

    return url