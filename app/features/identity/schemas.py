"""Identity verification schemas.

HTTP boundary models for the identity feature. These Pydantic classes
validate incoming requests and serialize outgoing responses. They
contain no business logic and no provider-specific fields.

Design decisions:
    * The client sends a Cloudinary ``public_id``, not a URL. The
      backend constructs the URL. This prevents SSRF, cross-account
      access, and URL injection — the client cannot tell the backend
      where to fetch data from.
    * The public ID must be prefixed with the KYC staging folder.
      The signed upload pins this folder, so a valid ID proves the
      asset originated from an authorized upload.
    * Responses carry a status enum, not a message. User-facing copy
      belongs to the frontend, which handles localization and display.
    * The full BVN, the face image, and the raw provider payload are
      never returned to the client.
"""

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import IDENTITY_BVN_LENGTH


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches Cloudinary's allowed public_id characters: alphanumerics,
# underscores, hyphens, dots, and "/" as the folder separator.
_PUBLIC_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")

# The folder the signed upload pins. A public ID outside this folder
# cannot have come from our signature endpoint.
_REQUIRED_PUBLIC_ID_PREFIX = "kyc-temp/"

# Cloudinary's public_id length limit is generous; 255 is a safe cap
# that blocks pathological inputs.
_MAX_PUBLIC_ID_LENGTH = 255


class VerificationStatus(StrEnum):
    """Public verification outcome.

    The frontend maps each value to its own localized copy.

    VERIFIED     Identity confirmed. The user may proceed.
    REJECTED     The check ran and failed. A retry may succeed if the
                 cause was image quality.
    WATCHLISTED  The record is flagged. Hard reject — no retry.
    NOT_FOUND    No record exists for the supplied ID.
    """

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    WATCHLISTED = "WATCHLISTED"
    NOT_FOUND = "NOT_FOUND"


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class VerifyIdentityRequest(BaseModel):
    """Payload for verifying a BVN alongside a facial image.

    The image itself is not sent to this endpoint — the client uploads
    it directly to Cloudinary using a signature from
    ``GET /identity/upload-signature``, then sends the resulting
    public ID here.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    bvn: str = Field(
        ...,
        min_length=IDENTITY_BVN_LENGTH,
        max_length=IDENTITY_BVN_LENGTH,
        description=f"{IDENTITY_BVN_LENGTH}-digit Bank Verification Number.",
        examples=["12345678901"],
    )
    cloudinary_public_id: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PUBLIC_ID_LENGTH,
        description=(
            "The public ID Cloudinary returned after the client uploaded "
            "the selfie using the signed payload from "
            "GET /identity/upload-signature."
        ),
        examples=["kyc-temp/abc123def456"],
    )

    @field_validator("bvn")
    @classmethod
    def _validate_bvn(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("BVN must contain only ASCII digits.")
        if value == "0" * IDENTITY_BVN_LENGTH:
            raise ValueError("BVN cannot be all zeros.")
        return value

    @field_validator("cloudinary_public_id")
    @classmethod
    def _validate_public_id(cls, value: str) -> str:
        if not value.startswith(_REQUIRED_PUBLIC_ID_PREFIX):
            raise ValueError(
                f"Public ID must start with '{_REQUIRED_PUBLIC_ID_PREFIX}'."
            )
        if ".." in value:
            raise ValueError("Public ID cannot contain '..'.")
        if not _PUBLIC_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "Public ID contains characters outside the allowed set."
            )
        return value


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class UploadSignatureResponse(BaseModel):
    """Signed payload the client uses to upload a selfie directly.

    The client POSTs these values plus the image file to Cloudinary's
    upload endpoint. The signature authorizes the upload and pins the
    folder and access mode — the client cannot override them.
    """

    model_config = ConfigDict(frozen=True)

    api_key: str = Field(..., description="Cloudinary API key.")
    cloud_name: str = Field(..., description="Cloudinary cloud name.")
    folder: str = Field(
        ...,
        description="Target folder for the upload.",
        examples=["kyc-temp"],
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp, signed.",
    )
    access_mode: Literal["authenticated"] = Field(
        ...,
        description="Always 'authenticated'. The asset is not publicly readable.",
        examples=["authenticated"],
    )
    signature: str = Field(
        ...,
        description="HMAC-SHA1 signature of the signed parameters.",
    )


class VerifyIdentityResponse(BaseModel):
    """Outcome of an identity verification attempt.

    The client switches on ``status`` and renders its own localized
    message. No user-facing copy is included — that belongs to the
    presentation layer.

    ``confidence`` carries the range constraint as a defense-in-depth
    guard: the adapter already validates that the provider returns a
    finite value in [0.0, 1.0], and the service sanitizes anything that
    slips through (e.g. from a stale Firestore record written before a
    scale change) to ``None`` before this model is constructed. The
    constraint is a safety net, not a normal failure path.
    """

    model_config = ConfigDict(frozen=True)

    status: VerificationStatus = Field(
        ...,
        description="Verification outcome. Map this to your own copy.",
    )
    confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Face match confidence between 0.0 and 1.0, or null if the "
            "provider did not return one, or if a stored value was "
            "outside the range and was sanitized by the service layer."
        ),
    )
    bvn_masked: str = Field(
        ...,
        description="The BVN with all but the last four digits masked.",
        examples=["*******8901"],
    )
    verified_at: datetime = Field(
        ...,
        description="UTC timestamp when the verification completed.",
    )