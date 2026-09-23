"""User endpoints.

HTTP surface for user profile lifecycle, verification flags, and PIN
management. Every route is authenticated — the uid always comes from
the verified Firebase token, never from the request body.

Response envelope (all routes):
    Success: {"success": True,  "data": {...}, "error": None}
    Failure: {"success": False, "data": None,  "error": {...}}
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.core.security import CurrentClaims, CurrentUid
from app.features.users import service
from app.features.users.schemas import (
    PhoneVerifyResponse,
    PinResetResponse,
    PinVerifyResponse,
    SetPinRequest,
    TagCheckResponse,
    TagClaimRequest,
    UpdateNamesRequest,
    UserCreateRequest,
    UserResponse,
    VerifyPhoneRequest,
    VerifyPinRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    """Wrap a response payload in the standard success envelope."""
    return {"success": True, "data": data, "error": None}


def _to_response(profile: dict[str, Any]) -> dict[str, Any]:
    """Project a stored user document into the public response shape.

    Derives ``pin_set`` from the presence of a stored PIN hash so the
    hash itself never leaves the backend. Any future field that must
    not be exposed adds its own derivation here.
    """
    projected = {
        "uid": profile["uid"],
        "first_name": profile.get("first_name", ""),
        "middle_name": profile.get("middle_name", ""),
        "last_name": profile.get("last_name", ""),
        "tag": profile.get("tag"),
        "country": profile["country"],
        "currency": profile["currency"],
        "phone": profile.get("phone", ""),
        "email": profile.get("email"),
        "email_verified": bool(profile.get("email_verified", False)),
        "phone_verified": bool(profile.get("phone_verified", False)),
        "identity_verified": bool(profile.get("identity_verified", False)),
        "account_number": profile["account_number"],
        "pin_set": bool(profile.get("pin_hash")),
        "avatar_url": profile.get("avatar_url"),
        "created_at": profile["created_at"],
    }
    return UserResponse(**projected).model_dump()


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.post(
    "/me",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create the authenticated user's NovaBanq profile",
    description=(
        "Called by the client after Firebase sign-up and email "
        "verification (or immediately for Google sign-in, which skips "
        "OTP). Generates and reserves a NovaBanq account number, stores "
        "the profile in Firestore, and returns it. Fails with 409 if a "
        "profile already exists for this uid, and 403 if the email has "
        "not been verified."
    ),
)
async def create_profile(
    uid: CurrentUid,
    claims: CurrentClaims,
    payload: UserCreateRequest,
) -> dict[str, Any]:
    profile = service.create_profile(
        uid,
        first_name=payload.first_name,
        middle_name=payload.middle_name,
        last_name=payload.last_name,
        country=payload.country,
        phone=payload.phone,
        email=claims.get("email"),
        claims=claims,
    )
    return _ok(_to_response(profile))


@router.get(
    "/me",
    response_model=dict,
    summary="Return the authenticated user's profile",
    description="Returns the NovaBanq profile for the current user.",
)
async def get_profile(uid: CurrentUid) -> dict[str, Any]:
    profile = service.get_profile(uid)
    return _ok(_to_response(profile))


@router.patch(
    "/me/names",
    response_model=dict,
    summary="Update the authenticated user's name fields",
    description=(
        "Replace first, middle, and last name. Rejected with 409 once "
        "identity verification has succeeded, because the verified "
        "names must match the government ID."
    ),
)
async def update_names(
    uid: CurrentUid,
    payload: UpdateNamesRequest,
) -> dict[str, Any]:
    profile = service.update_names(
        uid,
        first_name=payload.first_name,
        middle_name=payload.middle_name,
        last_name=payload.last_name,
    )
    return _ok(_to_response(profile))


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------

@router.get(
    "/me/tag/check",
    response_model=dict,
    summary="Check whether a tag is available for the current user",
    description=(
        "Appends the caller's country suffix (e.g. '.ng') to the supplied "
        "base name and reports whether the resulting full tag is already "
        "claimed. Read-only — does not reserve the tag. The frontend "
        "should debounce calls while the user types."
    ),
)
async def check_tag(
    uid: CurrentUid,
    tag: Annotated[str, Query(
        min_length=3,
        max_length=25,
        description="Base tag name without the country suffix.",
        examples=["david323"],
    )],
) -> dict[str, Any]:
    # Normalize the same way the claim endpoint does so both stay in sync.
    normalized = tag.lower().lstrip("@")
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]

    result = service.check_tag_available(uid, normalized)
    return _ok(TagCheckResponse(**result).model_dump())


@router.post(
    "/me/tag",
    response_model=dict,
    summary="Claim a @tag for the authenticated user",
    description=(
        "Assigns a globally unique @tag to the current user. The country "
        "suffix is appended server-side from the profile — the client "
        "sends only the base name. The full tag is normalized to "
        "lowercase and must not already be claimed. Returns the updated "
        "profile."
    ),
)
async def claim_tag(
    uid: CurrentUid,
    payload: TagClaimRequest,
) -> dict[str, Any]:
    profile = service.claim_tag(uid, payload.tag)
    return _ok(_to_response(profile))


# ---------------------------------------------------------------------------
# Verification flags
# ---------------------------------------------------------------------------

@router.post(
    "/me/phone/verify",
    response_model=dict,
    summary="Mark the authenticated user's phone as verified",
    description=(
        "Called after the client completes Firebase Phone Auth. The "
        "phone number is cross-checked against the profile's stored "
        "phone to prevent a token from another account from clearing "
        "verification here."
    ),
)
async def verify_phone(
    uid: CurrentUid,
    payload: VerifyPhoneRequest,
) -> dict[str, Any]:
    service.set_phone_verified(uid, payload.phone_number)
    return _ok(
        PhoneVerifyResponse(
            verified=True,
            phone_number=payload.phone_number,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# PIN
# ---------------------------------------------------------------------------

@router.post(
    "/me/pin",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Set the authenticated user's transaction PIN",
    description=(
        "Stores a bcrypt hash of the PIN. Fails with 409 if a PIN is "
        "already set — use the forgot-PIN flow to reset first."
    ),
)
async def set_pin(
    uid: CurrentUid,
    payload: SetPinRequest,
) -> dict[str, Any]:
    service.set_pin(uid, payload.pin)
    return _ok({"pin_set": True})


@router.post(
    "/me/pin/verify",
    response_model=dict,
    summary="Verify the authenticated user's transaction PIN",
    description=(
        "Compares the supplied PIN against the stored hash and enforces "
        "the lockout policy (5 failed attempts → 20-minute lock). "
        "Returns 429 with a retry delay when locked."
    ),
)
async def verify_pin(
    uid: CurrentUid,
    payload: VerifyPinRequest,
) -> dict[str, Any]:
    service.verify_pin_for_uid(uid, payload.pin)
    return _ok(PinVerifyResponse(verified=True).model_dump())


@router.post(
    "/me/pin/reset",
    response_model=dict,
    summary="Reset the authenticated user's transaction PIN",
    description=(
        "Final step of the forgot-PIN flow. The caller must present a "
        "fresh Firebase ID token obtained after a successful SMS "
        "verification; the token's phone_number claim is matched "
        "against the profile's stored phone. On success the PIN state "
        "is cleared and the user may set a new PIN via POST /me/pin."
    ),
)
async def reset_pin(
    uid: CurrentUid,
    claims: CurrentClaims,
) -> dict[str, Any]:
    service.reset_pin(uid, claims.get("phone_number"))
    return _ok(PinResetResponse(reset=True).model_dump())