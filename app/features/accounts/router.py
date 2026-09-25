"""Account endpoints.

HTTP surface for the accounts feature. One route:

    GET /accounts/me   — the authenticated user's balance

Every route is authenticated. The uid always comes from the verified
Firebase token, never from the request body.

Response envelope:
    Success: {"success": True,  "data": {...}, "error": None}
    Failure: {"success": False, "data": None,  "error": {...}}
"""

from typing import Any

from fastapi import APIRouter

from app.core.security import CurrentUid
from app.features.accounts import service

router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    """Wrap a response payload in the standard success envelope."""
    return {"success": True, "data": data, "error": None}


@router.get(
    "/me",
    response_model=dict[str, Any],
    summary="Return the authenticated user's account balance",
    description=(
        "Returns the user's single account — one currency, one balance. "
        "The account is created automatically on first access with a "
        "zero balance in the user's own currency. Subsequent calls "
        "return the existing account unchanged."
    ),
)
def get_account(uid: CurrentUid) -> dict[str, Any]:
    # Deliberately not `async def`: service.get_or_create_for_user runs
    # a blocking Firestore transaction with no awaitable anywhere in the
    # call chain. Declaring this a plain function lets FastAPI run it in
    # its threadpool, so the blocking Firestore round trip only occupies
    # its own thread instead of stalling the event loop for every other
    # in-flight request.
    account = service.get_or_create_for_user(uid)
    return _ok(account.model_dump())