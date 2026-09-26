"""Transfer schemas.

HTTP boundary models for the transfers feature. These define the
contract the mobile client codes against for both phases of a
transfer: the quote (shown before confirm) and the execute (run after
the PIN is verified).

The transfer flow is two requests:

    1. POST /transfers/quote  — resolve recipient, compute amounts,
                                 return what the user will confirm.
    2. POST /transfers        — execute against the ledger using the
                                 same inputs, returning the settled
                                 transaction.

The quote is a read — no money moves. The execute is the write. The
client is expected to send the same amount and recipient to both, and
the backend recomputes everything from scratch on execute. There is no
session state to reuse between the two calls; if the rate moved
between them, the execute uses the new rate, and the user's confirmation
of the quote is against a value that may be seconds old. That is the
correct trade-off: quotes are cheap and instant, and a two-minute-old
quote should never be honored.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    PIN_LENGTH,
    TRANSFER_MIN_AMOUNT_MINOR,
    Country,
    Currency,
)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

# Sender enters the full tag, including the country suffix. The backend
# looks it up verbatim — no suffix is appended server-side here. That
# matches how the recipient shared it (their profile's @tag field is
# already suffixed at claim time).
_TAG_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z]{2}$")


def _normalize_tag(value: str) -> str:
    """Normalize a recipient tag for lookup.

    Strips a leading '@' if the client sent one, lowercases the whole
    string, and validates the shape (base name + '.' + two-letter
    country suffix). The stored tag document is keyed by this exact
    normalized form, so a client sending "@David323.NG" and a client
    sending "david323.ng" both hit the same lookup.
    """
    normalized = value.strip().lower().lstrip("@")
    if not _TAG_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Tag must be in the form 'name.country', e.g. 'david323.ng'."
        )
    return normalized


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    """Payload for requesting a transfer quote.

    The sender's currency is NOT part of this payload — it's derived
    from their profile, which the backend loads from the authenticated
    token. Letting the client state its own currency would let a
    Nigerian user quote in cedis they don't hold.
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
            "minor units. Does not include the fee — the fee is "
            "computed on top and shown in the quote response. Must be "
            "at least the platform's minimum transfer amount."
        ),
        examples=[50000],
    )

    @field_validator("recipient_tag")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        return _normalize_tag(value)


class TransferRequest(BaseModel):
    """Payload for executing a transfer.

    This mirrors ``QuoteRequest`` and adds the two fields that only
    make sense on execute: the idempotency key and the sender's PIN.
    The client should generate the key once per transfer attempt and
    reuse it on retries; a retry with the same key returns the original
    result rather than moving money twice.
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
            "minor units. Must match the amount quoted, and must be at "
            "least the platform's minimum transfer amount."
        ),
        examples=[50000],
    )
    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description=(
            "Client-generated unique key for this transfer attempt. "
            "A retry with the same key returns the original result "
            "without moving money again."
        ),
        examples=["01HZX8V5K2N3P4Q5R6S7T8U9V0"],
    )
    pin: str = Field(
        ...,
        min_length=PIN_LENGTH,
        max_length=PIN_LENGTH,
        description=(
            f"{PIN_LENGTH}-digit transaction PIN the sender set during "
            "onboarding. Verified against the stored bcrypt hash; "
            "enforces the same lockout policy as POST /users/me/pin/verify."
        ),
        examples=["48392"],
    )

    @field_validator("recipient_tag")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        return _normalize_tag(value)

    @field_validator("pin")
    @classmethod
    def _validate_pin(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("PIN must contain only digits.")
        return value


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class RecipientSummary(BaseModel):
    """The recipient, as shown to the sender before confirm.

    Frozen because the sender never edits these — they're informational
    only. Everything here comes from the recipient's profile.

    Only the public identity of the recipient is exposed: tag, name,
    country, and currency. No balance, no account number, no
    verification flags. The sender has no business knowing whether the
    recipient has completed KYC.
    """

    model_config = ConfigDict(frozen=True)

    uid: str = Field(..., description="Recipient's Firebase uid.")
    tag: str = Field(
        ...,
        description="Recipient's full @tag, including country suffix.",
        examples=["david323.ng"],
    )
    display_name: str = Field(
        ...,
        description="Recipient's full name, joined from profile fields.",
        examples=["David Chukwuemeka Okafor"],
    )
    country: Country = Field(
        ...,
        description="Recipient's two-letter ISO country code.",
        examples=["NG"],
    )
    currency: Currency = Field(
        ...,
        description="Recipient's settlement currency.",
        examples=["NGN"],
    )


class QuoteResponse(BaseModel):
    """The quote shown to the sender before they confirm.

    Every amount the sender needs to see is here. The frontend renders
    this verbatim; it does not recompute anything.

    Amounts:
        ``send_amount_minor`` — what the sender entered (their currency).
        ``fee_minor``         — what NovaBanq charges (their currency).
        ``total_debit_minor`` — send + fee. What leaves their balance.
        ``receive_amount_minor`` — what the recipient gets (their currency).

    The frontend should display "You're sending {total_debit} ... which
    is {receive_amount} to {recipient.display_name}".
    """

    model_config = ConfigDict(frozen=True)

    sender_currency: Currency = Field(
        ...,
        description="Sender's currency (the one they pay in).",
    )
    recipient: RecipientSummary = Field(
        ...,
        description="Who the money is going to.",
    )
    send_amount_minor: int = Field(
        ...,
        ge=TRANSFER_MIN_AMOUNT_MINOR,
        description="Amount the sender entered, in sender-currency minor units.",
    )
    fee_minor: int = Field(
        ...,
        ge=0,
        description="Fee charged by NovaBanq, in sender-currency minor units.",
    )
    total_debit_minor: int = Field(
        ...,
        ge=1,
        description="Total debited from the sender: send + fee.",
    )
    receive_amount_minor: int = Field(
        ...,
        ge=1,
        description="Amount credited to the recipient, in recipient-currency minor units.",
    )
    rate: str = Field(
        ...,
        description=(
            "Exchange rate applied, as a decimal string, to the same "
            "precision the ledger actually stores (6 decimal places — "
            "see LEDGER_RATE_SCALE). 1 sender-currency unit = {rate} "
            "recipient-currency units. Never shown to more decimal "
            "places than the ledger preserves, so this figure always "
            "reconciles exactly with receive_amount_minor ÷ "
            "send_amount_minor."
        ),
        examples=["114.268230"],
    )
    expires_at: datetime = Field(
        ...,
        description=(
            "UTC timestamp after which this quote must be re-requested. "
            "The client should disable the confirm button after this "
            "time and prompt the user to refresh."
        ),
    )

    @model_validator(mode="after")
    def _verify_total_debit(self) -> "QuoteResponse":
        """Enforce the invariant the docstring promises but Pydantic
        won't check on its own: total_debit_minor must equal
        send_amount_minor + fee_minor. A response that fails this is a
        bug in whatever computed the quote, not a client error — fail
        loudly here rather than silently shipping a quote whose numbers
        don't add up.
        """
        expected = self.send_amount_minor + self.fee_minor
        if self.total_debit_minor != expected:
            raise ValueError(
                f"total_debit_minor ({self.total_debit_minor}) must equal "
                f"send_amount_minor + fee_minor ({expected})."
            )
        return self


class TransferResponse(BaseModel):
    """The result of a settled transfer.

    Returned after the ledger has committed. ``transaction_id`` is the
    ledger's transaction identifier — the client uses it to fetch the
    full transaction later, or to display a receipt.

    ``quote`` is the recomputed quote that was actually applied. It may
    differ slightly from the quote the client showed the user if the
    rate moved between the two calls; the client should treat this as
    the authoritative result and show it on the receipt.
    """

    model_config = ConfigDict(frozen=True)

    transaction_id: str = Field(
        ...,
        description="Ledger transaction identifier.",
        examples=["01HZX8V5K2N3P4Q5R6S7T8U9V0"],
    )
    status: Literal["SETTLED"] = Field(
        ...,
        description=(
            "Settlement status. Always 'SETTLED' — under the ledger's "
            "current single-shot commit model, a transfer that doesn't "
            "settle raises an error instead of returning a response, so "
            "this field has no other reachable value on a 200 response."
        ),
        examples=["SETTLED"],
    )
    quote: QuoteResponse = Field(
        ...,
        description="The quote that was applied, recomputed at execution time.",
    )
    settled_at: datetime = Field(
        ...,
        description="UTC timestamp when the ledger committed the transfer.",
    )