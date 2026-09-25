"""Identity verification endpoints.

HTTP surface for the identity feature. Two routes:

    GET  /identity/upload-signature   — signed payload for direct upload
    POST /identity/verify             — BVN + face verification

Every route is authenticated. The uid always comes from the verified
Firebase token, never from the request body.

Response envelope (all routes):
    Success: {"success": True,  "data": {...}, "error": None}
    Failure: {"success": False, "data": None,  "error": {...}}
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks

from app.core.security import CurrentUid
from app.features.identity import service
from app.features.identity.schemas import (
    UploadSignatureResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)
from app.infra.cloudinary_client import generate_upload_signature

logger = logging.getLogger(__name__)

router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    """Wrap a response payload in the standard success envelope."""
    return {"success": True, "data": data, "error": None}


@router.get(
    "/upload-signature",
    response_model=dict,
    summary="Get a signed payload for direct Cloudinary upload",
    description=(
        "Returns a short-lived signed payload the mobile client uses to "
        "upload the KYC selfie directly to Cloudinary. The backend never "
        "handles image bytes. The signature pins the folder and access "
        "mode — the client cannot override them. After uploading, the "
        "client sends the resulting public id to POST /identity/verify."
    ),
)
def get_upload_signature(uid: CurrentUid) -> dict[str, Any]:
    payload = generate_upload_signature()
    return _ok(UploadSignatureResponse(**payload).model_dump())


@router.post(
    "/verify",
    response_model=dict,
    summary="Verify the authenticated user's BVN and selfie",
    description=(
        "Runs BVN + face verification against the uploaded selfie. The "
        "image is fetched from Cloudinary via a signed URL and deleted "
        "after the check completes, regardless of outcome. On success, "
        "the user profile's identity_verified flag is set. Once "
        "verified, a user cannot re-run this endpoint."
    ),
)
def verify_identity(
    uid: CurrentUid,
    payload: VerifyIdentityRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    result = service.verify_bvn_with_face(
        uid=uid,
        bvn=payload.bvn,
        cloudinary_public_id=payload.cloudinary_public_id,
        background_tasks=background_tasks,
    )
    return _ok(VerifyIdentityResponse(**result).model_dump())