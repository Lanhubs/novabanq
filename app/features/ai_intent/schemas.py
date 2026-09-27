"""AI intent schemas.

HTTP boundary models for the AI intent feature. The user types a
natural-language instruction like "send 5000 to david.ng at 5pm" and
the endpoint returns a structured intent plus everything the frontend
needs to render a confirmation screen.

Two models:

    * ``ParseIntentRequest`` — the raw text the user typed.
    * ``ParseIntentResponse`` — the extracted fields, the resolved
      recipient, and the full transfer quote.

The response carries the full quote (the same shape
``POST /transfers/quote`` returns) so the frontend can render the
confirmation screen from a single call. When the user confirms, the
frontend executes via the existing ``POST /transfers`` endpoint
using the fields from this response.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.features.transfers.schemas import QuoteResponse


class ParseIntentRequest(BaseModel):
    """The user's natural-language instruction.

    Deliberately unconstrained beyond a length cap — the whole point
    is to accept whatever the user types. The AI layer is what
    extracts structure; the schema just carries the raw text.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description=(
            "The user's instruction, verbatim. Examples: "
            "'send 5000 to david.ng', "
            "'help me transfer 250 cedis to kwame.gh', "
            "'send 5000 to david.ng at 5pm'."
        ),
        examples=["send 5000 to david.ng"],
    )


class ParsedIntent(BaseModel):
    """The structured intent the AI extracted from the text.

    Frozen so the frontend can't mutate it. Every field other than
    ``action`` and ``amount_major`` may be absent if the user's text
    didn't include it — e.g. a user who types "send 5000 to david.ng"
    with no time reference gets ``execute_at=None``.
    """

    model_config = ConfigDict(frozen=True)

    action: str = Field(
        ...,
        description=(
            "The action the user asked for. Currently always "
            "``'transfer'`` — this field exists so future intents "
            "(check balance, request money) can be added without a "
            "schema change."
        ),
        examples=["transfer"],
    )
    amount_major: Decimal = Field(
        ...,
        gt=0,
        description=(
            "The amount the user specified, in the **sender's currency** "
            "major units (e.g. 5000 for ₦5,000, 19.99 for ₦19.99). "
            "Converted to minor units by the service before being "
            "handed to the ledger. A ``Decimal``, not a float, for the "
            "same reason the rest of the money-handling code is: it "
            "must reach the ledger with no binary rounding error."
        ),
        examples=["5000"],
    )
    recipient_tag: str = Field(
        ...,
        description=(
            "The recipient's tag, including country suffix. "
            "Normalized to lowercase, leading '@' stripped."
        ),
        examples=["david.ng"],
    )
    execute_at: datetime | None = Field(
        None,
        description=(
            "When the transfer should execute, if the user specified "
            "a time. Null for immediate transfers. Timezone is UTC; "
            "the AI is instructed to interpret the user's local time "
            "in the sender's country and convert to UTC."
        ),
        examples=["2026-09-27T17:00:00Z"],
    )


class ParseIntentResponse(BaseModel):
    """The full response the frontend uses to render confirmation.

    Carries three things:

        1. ``intent`` — the raw fields the AI extracted.
        2. ``quote`` — the full transfer quote (same shape as
           ``POST /transfers/quote``), which resolves the recipient's
           full name, computes the fee, and shows the exchange rate.
        3. ``requested_text`` — the original user text, echoed back
           so the frontend doesn't have to keep it separately.

    The frontend renders the confirmation screen from ``quote`` and
    ``requested_text``. When the user taps confirm, it calls
    ``POST /transfers`` with the amount and recipient from ``quote``,
    a fresh idempotency key, and the user's PIN.

    ``execute_at`` on the intent being non-null means the frontend
    should route the user toward the *scheduled* transfer flow
    instead of the immediate one. That flow lives in a different
    endpoint (added in a subsequent phase).
    """

    model_config = ConfigDict(frozen=True)

    intent: ParsedIntent = Field(
        ...,
        description="The structured fields the AI extracted.",
    )
    quote: QuoteResponse = Field(
        ...,
        description=(
            "The full transfer quote, computed against the current FX "
            "rate. Same shape as ``POST /transfers/quote`` returns. "
            "Includes the resolved recipient's full name, the fee, "
            "the total debit, and the recipient's receive amount."
        ),
    )
    requested_text: str = Field(
        ...,
        description="The original text the user typed, echoed back.",
        examples=["send 5000 to david.ng"],
    )