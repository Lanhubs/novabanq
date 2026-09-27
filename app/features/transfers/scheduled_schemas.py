"""Scheduled-transfer schemas.

HTTP boundary models for the scheduled-transfer feature. Three models:

    * ``ScheduleTransferRequest`` — what the client posts to
      ``POST /transfers/scheduled``. Same fields as the immediate
      transfer, plus an ``execute_at`` timestamp.
    * ``ScheduledTransferResponse`` — what comes back. Describes the
      scheduled transfer from the caller's perspective.
    * ``ScheduledTransferListResponse`` — a list of the caller's
      scheduled transfers, for the "upcoming transfers" screen.

A scheduled transfer is created by ``POST /transfers/scheduled`` and
executed later by the scheduler. The scheduler calls the transfers
service's ``execute_pre_authorized`` function, which skips PIN
verification because the PIN was already checked at scheduling time.
See ``app.features.transfers.service`` for that contract.
"""

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    PIN_LENGTH,
    TRANSFER_MIN_AMOUNT_MINOR,
    Currency,
    ScheduledTransferStatus,
)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

# Duplicated from app.features.transfers.schemas rather than imported —
# that module's _normalize_tag is private by convention, and reaching
# across modules for an underscore-prefixed name is worse than a small,
# clearly-flagged duplication. If a third caller ever needs tag
# normalization, promote it to a shared, public location instead of
# duplicating a third time.
_TAG_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z]{2}$")


def _normalize_tag(value: str) -> str:
    """Normalize a recipient tag for lookup.

    Strips a leading '@' if the client sent one, lowercases the whole
    string, and validates the shape (base name + '.' + two-letter
    country suffix).
    """
    normalized = value.strip().lower().lstrip("@")
    if not _TAG_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Tag must be in the form 'name.country', e.g. 'david323.ng'."
        )
    return normalized


class ScheduleTransferRequest(BaseModel):
    """Payload for scheduling a transfer to execute in the future.

    Mirrors the immediate-transfer request (``TransferRequest``) with
    two changes:

        * ``execute_at`` is required — this is a scheduled transfer,
          so the caller must say when it should run.
        * ``pin`` is still required — the PIN is verified now, at
          scheduling time, when the user is present to be challenged.
          The scheduler will not re-verify it, because the PIN is gone
          by the time the transfer fires.

    ``execute_at`` must be in the future. A timestamp in the past is
    rejected at validation time — the point of a scheduled transfer is
    that it hasn't happened yet.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recipient_tag: str = Field(
        ...,
        description=(
            "Full tag of the recipient including the country suffix, "
            "e.g. 'david323.ng'. A leading '@' is accepted and stripped."
        ),
        examples=["david323.ng"],
    )
    amount_minor: int = Field(
        ...,
        ge=TRANSFER_MIN_AMOUNT_MINOR,
        description=(
            "Amount the sender is sending, in their own currency's "
            "minor units. Must be at least the platform's minimum "
            "transfer amount."
        ),
        examples=[50000],
    )
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description=(
            "Client-generated unique key for this scheduling attempt. "
            "A retry with the same key returns the original scheduled "
            "transfer without creating a second one."
        ),
        examples=["01HZX8V5K2N3P4Q5R6S7T8U9V0"],
    )
    pin: str = Field(
        ...,
        min_length=PIN_LENGTH,
        max_length=PIN_LENGTH,
        description=(
            f"The user's {PIN_LENGTH}-digit transaction PIN. Verified "
            "now, at scheduling time; the scheduler will not "
            "re-verify it."
        ),
        examples=["48392"],
    )
    execute_at: datetime = Field(
        ...,
        description=(
            "When the transfer should execute, in UTC. Must be in the "
            "future. The scheduler fires the transfer within a short "
            "window after this time (see "
            "SCHEDULED_TRANSFER_FIRE_WINDOW_MINUTES)."
        ),
        examples=["2026-09-28T17:00:00Z"],
    )

    @field_validator("recipient_tag")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        return _normalize_tag(value)

    @field_validator("pin")
    @classmethod
    def _validate_pin_digits(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("PIN must contain only digits.")
        return value

    @field_validator("execute_at")
    @classmethod
    def _validate_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execute_at must include a timezone (UTC).")
        if value <= datetime.now(timezone.utc):
            raise ValueError("execute_at must be in the future.")
        return value


class ScheduledTransferResponse(BaseModel):
    """A scheduled transfer, from the caller's perspective.

    Returned by both the create endpoint and the list endpoint, so the
    frontend renders the "upcoming transfers" list with the same
    component.
    """

    model_config = ConfigDict(frozen=True)

    scheduled_transfer_id: str = Field(
        ...,
        description="Identifier of this scheduled transfer.",
        examples=["01HZX8V5K2N3P4Q5R6S7T8U9V0"],
    )
    recipient_tag: str = Field(
        ...,
        description="Recipient's tag.",
        examples=["david323.ng"],
    )
    recipient_display_name: str | None = Field(
        None,
        description=(
            "Recipient's full display name, resolved at list time. "
            "Null if the recipient profile has since been deleted."
        ),
        examples=["Eze David Chinedu"],
    )
    amount_minor: int = Field(
        ...,
        ge=TRANSFER_MIN_AMOUNT_MINOR,
        description="Amount to send, in the sender's currency, minor units.",
        examples=[50000],
    )
    sender_currency: Currency = Field(
        ...,
        description="The sender's currency at scheduling time.",
        examples=["GHS"],
    )
    execute_at: datetime = Field(
        ...,
        description="When the transfer is scheduled to run, in UTC.",
    )
    status: ScheduledTransferStatus = Field(
        ...,
        description=(
            "Current state of the scheduled transfer. PENDING means "
            "it hasn't fired yet; SETTLED, FAILED, and CANCELLED are "
            "terminal."
        ),
        examples=["PENDING"],
    )
    transaction_id: str | None = Field(
        None,
        description=(
            "The underlying ledger transaction id, populated once the "
            "scheduler has fired the transfer and it settled. Null "
            "while PENDING, and also null for FAILED or CANCELLED — "
            "under the ledger's single-shot commit model, an attempt "
            "that doesn't settle writes nothing, so there is no "
            "transaction to reference."
        ),
    )
    failure_reason: str | None = Field(
        None,
        description=(
            "If status is FAILED, the error code that caused the "
            "failure — e.g. 'INSUFFICIENT_BALANCE'. Null otherwise."
        ),
        examples=["INSUFFICIENT_BALANCE"],
    )
    created_at: datetime = Field(
        ...,
        description="When the schedule was created, in UTC.",
    )

    @model_validator(mode="after")
    def _verify_status_consistency(self) -> "ScheduledTransferResponse":
        """Enforce the field-presence rules the docstrings above state
        but Pydantic won't check on its own — mirrors the equivalent
        check on TransactionDocument and QuoteResponse elsewhere in
        this codebase.
        """
        if self.status is ScheduledTransferStatus.FAILED:
            if self.failure_reason is None:
                raise ValueError(
                    "failure_reason is required when status is FAILED."
                )
        elif self.failure_reason is not None:
            raise ValueError(
                f"failure_reason must be None when status is "
                f"{self.status.value}."
            )

        if self.status is ScheduledTransferStatus.SETTLED:
            if self.transaction_id is None:
                raise ValueError(
                    "transaction_id is required when status is SETTLED."
                )
        elif self.transaction_id is not None:
            raise ValueError(
                f"transaction_id must be None when status is "
                f"{self.status.value}."
            )

        return self


class ScheduledTransferListResponse(BaseModel):
    """A page of the caller's scheduled transfers.

    No pagination for now — a user's upcoming-transfers list is small
    enough that fetching all of them at once is fine. If that changes,
    a cursor field goes here without breaking the shape.
    """

    model_config = ConfigDict(frozen=True)

    items: list[ScheduledTransferResponse] = Field(
        ...,
        description=(
            "The caller's scheduled transfers, newest first. Includes "
            "past ones — filter on ``status`` client-side to show only "
            "pending."
        ),
    )