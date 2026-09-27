"""AI execute-transfer schemas.

HTTP boundary models for the combined AI execute-transfer endpoint.
One endpoint, two possible response shapes, discriminated by a
``kind`` field:

    * ``ImmediateTransferResult`` — the parsed intent had no
      ``execute_at``, so the transfer ran through the standard
      immediate-transfer path. Carries the ``TransferResponse``.
    * ``ScheduledTransferResult`` — the parsed intent included a
      future time, so a scheduled transfer was created instead.
      Carries the ``ScheduledTransferResponse``.

A client consuming this endpoint switches on ``data.kind``. In Dart
(the language of this project's mobile client):

    if (data['kind'] == 'IMMEDIATE') {
      final transfer = TransferResponse.fromJson(data['transfer']);
      // ...show the receipt
    } else if (data['kind'] == 'SCHEDULED') {
      final scheduled = ScheduledTransferResponse.fromJson(
        data['scheduled_transfer'],
      );
      // ...show the "scheduled" confirmation
    }

The discriminated union means Pydantic emits the correct variant
schema in the OpenAPI docs, and the frontend dev sees both shapes
in ``/docs`` rather than a bare ``object``.

Optional recipient confirmation:
    ``ExecuteTransferRequest.confirmed_recipient_uid`` is optional.
    When provided, the service resolves the recipient tag as usual
    and rejects the request if the resolved uid does not match. That
    lets a cautious frontend do the two-step flow — call
    ``/ai/parse-transfer`` first, show the recipient name, then call
    this endpoint with the uid the user actually confirmed — without
    needing a separate endpoint. A frontend that wants the fast path
    omits the field and accepts that the recipient is whoever the
    tag resolves to at execution time.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PIN_LENGTH
from app.features.transfers.scheduled_schemas import ScheduledTransferResponse
from app.features.transfers.schemas import TransferResponse


class ExecuteTransferRequest(BaseModel):
    """The user's natural-language instruction, plus their PIN.

    The PIN is here rather than on a separate confirm step because the
    whole point of this endpoint is to let the frontend avoid a
    multi-call flow: the user types what they want, the backend parses
    it, verifies the PIN, and executes. For a two-step UI that shows
    the recipient name before committing, the frontend calls
    ``/ai/parse-transfer`` first and then includes
    ``confirmed_recipient_uid`` here.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description=(
            "The user's instruction, verbatim. Examples: "
            "'send 5000 to david.ng', "
            "'help me transfer 250 cedis to kwame.gh at 5pm'."
        ),
        examples=["send 5000 to david.ng"],
    )
    pin: str = Field(
        ...,
        min_length=PIN_LENGTH,
        max_length=PIN_LENGTH,
        description=(
            f"The user's {PIN_LENGTH}-digit transaction PIN. Verified "
            "before the transfer is executed or scheduled."
        ),
        examples=["48392"],
    )
    confirmed_recipient_uid: str | None = Field(
        None,
        min_length=1,
        description=(
            "Optional. If provided, the resolved recipient's uid must "
            "match this value or the request is rejected. A cautious "
            "frontend uses this after showing the recipient name on a "
            "confirm screen; a fast-path frontend omits it and trusts "
            "the tag resolution at execution time. An empty string is "
            "rejected at validation time — pass ``null`` to omit, not "
            "``\"\"``."
        ),
        examples=["RH2cWAvBQbSlCyXoI5zGxssMwPb2"],
    )

    @field_validator("pin")
    @classmethod
    def _validate_pin_digits(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("PIN must contain only digits.")
        return value


class ImmediateTransferResult(BaseModel):
    """The immediate-transfer arm of the discriminated union.

    ``kind`` is fixed to ``"IMMEDIATE"`` so Pydantic can route an
    incoming dict to the correct variant when the frontend's generated
    client deserializes a response.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["IMMEDIATE"] = "IMMEDIATE"
    transfer: TransferResponse = Field(
        ...,
        description=(
            "The settled transfer, exactly as "
            "``POST /transfers`` returns it."
        ),
    )


class ScheduledTransferResult(BaseModel):
    """The scheduled-transfer arm of the discriminated union."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["SCHEDULED"] = "SCHEDULED"
    scheduled_transfer: ScheduledTransferResponse = Field(
        ...,
        description=(
            "The created schedule, exactly as "
            "``POST /transfers/scheduled`` returns it."
        ),
    )


# The full response payload — a discriminated union of the two arms
# above. Pydantic uses the ``kind`` field as the discriminator, which
# means:
#   * A response dict is validated against the correct arm based on
#     ``kind``.
#   * The OpenAPI schema published at /docs shows both arms as named
#     variants, so the frontend dev can see exactly which fields are
#     present in each case.
ExecuteTransferPayload = Annotated[
    ImmediateTransferResult | ScheduledTransferResult,
    Field(discriminator="kind"),
]