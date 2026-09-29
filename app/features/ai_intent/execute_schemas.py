"""AI execute-transfer schemas.

HTTP boundary models for the /ai/execute-transfer endpoint. This
endpoint settles a transfer the user already confirmed from the AI
chat or from a parse-transfer preview.

The request takes the **structured fields** the user confirmed, not
the user's original natural-language text. Re-parsing the text with a
second Gemini call at execute time would reintroduce the exact class
of drift the confirm step exists to prevent — the amount that settles
must be the amount the user was shown, full stop. See
``ai_intent.confirm_execute``'s module docstring for the reasoning.

The response is a discriminated union by ``kind``:

    * ``kind == "IMMEDIATE"`` — the transfer settled. The full
      ``TransferResponse`` is in ``transfer``.
    * ``kind == "SCHEDULED"`` — a scheduled-transfer document was
      created. The full ``ScheduledTransferResponse`` is in
      ``scheduled_transfer``.

A client consuming this endpoint switches on ``kind``. In Dart:

    if (data['kind'] == 'IMMEDIATE') {
      final transfer = TransferResponse.fromJson(data['transfer']);
      // ...show the receipt
    } else if (data['kind'] == 'SCHEDULED') {
      final scheduled = ScheduledTransferResponse.fromJson(
        data['scheduled_transfer'],
      );
      // ...show the scheduled confirmation
    }

Why ``AiExecuteTransferResult`` has both arms nullable instead of
using an ``Annotated[...|..., Field(discriminator=...)]`` union the
way the older ``ExecuteTransferPayload`` did:

    The service layer (``confirm_execute.execute_confirmed_transfer``)
    returns an instance of this model directly; it does not construct
    two separate variant classes. Making it one class with one
    populated arm and one null arm keeps the service return type and
    the HTTP response model identical, so the router can pass the
    service's output through unchanged. The trade-off is a slightly
    wider OpenAPI schema; the upside is one fewer translation layer
    and one fewer class to keep in sync.

Required fields on the request:

    * ``recipient_tag`` / ``amount_minor`` / ``execute_at`` — the
      already-computed fields from the confirm step.
    * ``confirmed_recipient_uid`` — the recipient's uid as shown to
      the user. **Required**, not optional: the whole safety property
      of the confirm/execute split depends on re-verifying that the
      tag still resolves to this uid at execute time.
    * ``idempotency_key`` — client-generated. A retry after a
      dropped connection must not settle twice.
    * ``pin`` — the user's transaction PIN. Verified here, before any
      money moves; never sent to the language model.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PIN_LENGTH, TRANSFER_MIN_AMOUNT_MINOR
from app.features.transfers.scheduled_schemas import ScheduledTransferResponse
from app.features.transfers.schemas import TransferResponse


class ExecuteTransferRequest(BaseModel):
    """The fields of a transfer the user has already confirmed.

    Every field here comes directly from the confirmation payload the
    backend returned to the frontend, unchanged. The frontend does not
    compute any of them; it echoes them back with the user's PIN and a
    fresh idempotency key.

    The absence of a ``text`` field is deliberate. A second parse of
    the user's original sentence at execute time is not safe — see the
    module docstring.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recipient_tag: str = Field(
        ...,
        min_length=1,
        description=(
            "Recipient's full @tag, including country suffix, exactly "
            "as returned by the confirm step. A leading '@' is "
            "accepted and stripped."
        ),
        examples=["david.ng"],
    )
    amount_minor: int = Field(
        ...,
        ge=TRANSFER_MIN_AMOUNT_MINOR,
        description=(
            "Amount the sender is sending, in their own currency's "
            "minor units, exactly as returned by the confirm step. "
            "Must match the amount the user was shown — the service "
            "does not re-derive this from any other source."
        ),
        examples=[50000],
    )
    confirmed_recipient_uid: str = Field(
        ...,
        min_length=1,
        description=(
            "The recipient's uid as shown to the user on the confirm "
            "screen. Required. The service re-resolves the tag at "
            "execute time and rejects the request if the tag no "
            "longer resolves to this uid — the case where the tag "
            "changed hands between confirmation and execution."
        ),
        examples=["RH2cWAvBQbSlCyXoI5zGxssMwPb2"],
    )
    execute_at: datetime | None = Field(
        None,
        description=(
            "When the transfer should execute, if the user asked "
            "for a future time. Null for immediate transfers."
        ),
        examples=["2026-09-28T17:00:00Z"],
    )
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description=(
            "Client-generated unique key for this execute attempt. "
            "A retry with the same key returns the original result "
            "without settling twice. Required — see the module "
            "docstring for why every money-moving endpoint has this."
        ),
        examples=["01HZX8V5K2N3P4Q5R6S7T8U9V0"],
    )
    pin: str = Field(
        ...,
        min_length=PIN_LENGTH,
        max_length=PIN_LENGTH,
        description=(
            f"The user's {PIN_LENGTH}-digit transaction PIN. Verified "
            "before the transfer is executed or scheduled. Never sent "
            "to the language model."
        ),
        examples=["48392"],
    )

    @field_validator("pin")
    @classmethod
    def _validate_pin_digits(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("PIN must contain only digits.")
        return value


class AiExecuteTransferResult(BaseModel):
    """The response payload for a successful execute-transfer call.

    One class, two arms — ``kind`` says which arm is populated. The
    other arm is always present but ``None``. This mirrors the
    service-layer return type from
    ``confirm_execute.execute_confirmed_transfer``, so the router can
    return the service's result without a translation step.

    Frozen — the response is a read-only projection.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["IMMEDIATE", "SCHEDULED"] = Field(
        ...,
        description=(
            "Which arm is populated. 'IMMEDIATE' means the transfer "
            "settled; 'SCHEDULED' means a scheduled-transfer document "
            "was created."
        ),
        examples=["IMMEDIATE"],
    )
    transfer: TransferResponse | None = Field(
        None,
        description=(
            "Populated when ``kind == 'IMMEDIATE'``. The settled "
            "transfer, exactly as ``POST /transfers`` returns it."
        ),
    )
    scheduled_transfer: ScheduledTransferResponse | None = Field(
        None,
        description=(
            "Populated when ``kind == 'SCHEDULED'``. The created "
            "schedule, exactly as ``POST /transfers/scheduled`` "
            "returns it."
        ),
    )