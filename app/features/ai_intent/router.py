"""AI intent HTTP endpoints.

One endpoint: `POST /ai/parse-transfer`. Takes a natural-language
instruction, runs it through Gemini, and returns a structured intent
plus the full transfer quote the frontend needs to render the
confirmation screen.

Authenticated the same way as every other user-facing endpoint — a
Firebase ID token. The sender's uid is needed because the amount
parsed from the user's text is in their currency, and the timezone
is theirs, so both must be read from their profile before the
parsing can be validated.
"""

from typing import Any

from fastapi import APIRouter

from app.core.security import CurrentUid
from app.features.ai_intent import service
from app.features.ai_intent.schemas import (
    ParseIntentRequest,
    ParseIntentResponse,
)

router = APIRouter()


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


@router.post(
    "/ai/parse-transfer",
    response_model=dict[str, Any],
    summary="Parse a natural-language transfer instruction",
    description=(
        "Takes a user's instruction — 'send 5000 to david.ng' or "
        "'help me transfer 250 cedis to kwame.gh at 5pm' — and "
        "returns the structured intent (amount, recipient, optional "
        "scheduled time) plus the full transfer quote. The frontend "
        "renders the confirmation screen from the quote, then calls "
        "`POST /transfers` with the fields from the response when the "
        "user confirms.\n\n"
        "The recipient is resolved here, so the confirmation screen "
        "can show the recipient's full name before the user commits — "
        "the entire point of surfacing the intent back to the user "
        "before any money moves.\n\n"
        "If `intent.execute_at` is non-null, the user asked for a "
        "scheduled transfer. The immediate-transfer flow (`POST "
        "/transfers`) ignores that field, so the frontend should "
        "route scheduled intents to the scheduled-transfer endpoint "
        "instead."
    ),
)
def parse_transfer_intent(
    uid: CurrentUid,
    payload: ParseIntentRequest,
) -> dict[str, Any]:
    """Parse the user's text into a structured intent + quote.

    Dumped with ``mode="json"``, not the bare ``model_dump()`` default.
    ``response_model`` here is ``dict[str, Any]``, so FastAPI has no
    field-level type info for anything nested inside ``data`` and
    falls back to its generic encoder for serialization. That generic
    encoder converts a live ``Decimal`` to ``float`` — exactly the
    precision loss ``amount_major`` was made ``Decimal`` to avoid.
    Dumping in JSON mode first lets pydantic serialize ``Decimal`` as
    an exact string itself, before the generic encoder ever sees it.
    """
    result: ParseIntentResponse = service.parse_transfer_intent(
        sender_uid=uid,
        text=payload.text,
    )
    return _ok(result.model_dump(mode="json"))