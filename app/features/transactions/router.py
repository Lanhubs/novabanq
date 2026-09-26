"""Transaction history and receipt endpoints."""

from typing import Any

from fastapi import APIRouter, Query

from app.core.security import CurrentUid
from app.features.transactions import service
from app.features.transactions.schemas import (
    TransactionListResponse,
    TransactionSummary,
)

router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List the authenticated user's transaction history",
    description=(
        "Returns a page of the caller's transactions, newest first — "
        "both sent and received. Each item describes the transaction "
        "from the caller's perspective: direction (IN or OUT) and the "
        "counterparty (the other party, never the caller)."
    ),
)
def list_transactions(
    uid: CurrentUid,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    result: TransactionListResponse = service.list_for_user(uid, limit=limit)
    return _ok(result.model_dump())


@router.get(
    "/{transaction_id}",
    response_model=dict[str, Any],
    summary="Fetch a single transaction",
    description=(
        "Returns a single transaction the caller participated in. A "
        "caller who is neither the sender nor the recipient gets a 404, "
        "same as if the id didn't exist."
    ),
)
def get_transaction(
    uid: CurrentUid,
    transaction_id: str,
) -> dict[str, Any]:
    result: TransactionSummary = service.get_receipt(
        transaction_id,
        caller_uid=uid,
    )
    return _ok(result.model_dump())