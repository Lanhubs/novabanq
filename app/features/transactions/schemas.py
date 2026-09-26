"""Transaction history schemas.

HTTP boundary models for the transactions feature. Two things are
exposed here:

    * ``TransactionSummary`` — one row in the history list. Compact,
      enough to render a list item, no ledger internals.
    * ``TransactionListResponse`` — one page of summaries plus a
      cursor for the next page.

The receipt endpoint returns a ``TransactionSummary`` with all fields
populated; the list endpoint returns the same shape so the client can
reuse the rendering code. There is no separate "full detail" model
today — when the receipt needs more fields than the list does, add
them to this schema and mark them optional for the list case.

Privacy model: only the counterparty's ``uid``, ``tag``, and ``name``
are exposed. The caller's own snapshot is never echoed back — they
know who they are. No balance, no KYC status, no account number of
either party appears in any response.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import Currency, TransactionStatus, TransactionType


class TransactionParty(BaseModel):
    """The other party in a transaction, as seen by the caller.

    Every field is optional except ``uid`` because the ledger's
    snapshots are populated from the profile at the moment the
    transaction settles, and a profile could theoretically be missing
    a tag (a user who onboarded without claiming one) or a name
    (extremely unlikely, but the storage layer tolerates it). The
    frontend falls back to ``uid`` when ``tag`` or ``name`` is absent.
    """

    model_config = ConfigDict(frozen=True)

    uid: str = Field(
        ...,
        description="Firebase uid of the counterparty.",
    )
    tag: str | None = Field(
        None,
        description=(
            "The counterparty's full @tag at the time of the "
            "transaction, including country suffix. Null if they had "
            "no tag at settlement time."
        ),
        examples=["davidkampe.gh"],
    )
    name: str | None = Field(
        None,
        description=(
            "The counterparty's display name at the time of the "
            "transaction. Null if the snapshot didn't carry a name."
        ),
        examples=["David Chashama Mensah"],
    )


class TransactionSummary(BaseModel):
    """One transaction, from the caller's perspective.

    ``direction`` is derived, not stored: it's ``IN`` when the caller
    is the recipient and ``OUT`` when the caller is the sender. The
    same underlying transaction document produces opposite directions
    for its two participants, which is correct — Kwame sent it, Temi
    received it, and both should see it as such.

    The amount fields are the amounts *as stored on the transaction*,
    not adjusted for the caller's perspective. A recipient viewing a
    transfer they received sees ``from_amount_minor`` as the amount
    the sender sent (in the sender's currency) and ``to_amount_minor``
    as the amount they received (in their own currency). The frontend
    picks whichever is meaningful for the row it's rendering.
    """

    model_config = ConfigDict(frozen=True)

    transaction_id: str = Field(
        ...,
        description="Ledger transaction identifier.",
        examples=["1b9a1064-43f9-4581-b092-72261fe3c0ee"],
    )
    transaction_type: TransactionType = Field(
        ...,
        description=(
            "High-level category. ``TRANSFER`` is person-to-person, "
            "``FUNDING`` is money-in from outside the ledger, "
            "``WITHDRAWAL`` is money-out, ``REVERSAL`` inverts an "
            "earlier transaction."
        ),
        examples=["TRANSFER"],
    )
    direction: Literal["IN", "OUT"] = Field(
        ...,
        description=(
            "``IN`` when the caller received money, ``OUT`` when they "
            "sent it. Derived from which side of the transaction the "
            "caller is on."
        ),
        examples=["OUT"],
    )
    status: TransactionStatus = Field(
        ...,
        description=(
            "Always ``SETTLED`` for any transaction visible in a "
            "user's history — the ledger writes nothing else. The "
            "field exists for forward compatibility."
        ),
        examples=["SETTLED"],
    )
    counterparty: TransactionParty | None = Field(
        None,
        description=(
            "The other party, from the caller's perspective. Null for "
            "FUNDING received (money enters from outside the ledger) "
            "and for WITHDRAWAL sent (money leaves the ledger)."
        ),
    )
    from_currency: Currency | None = Field(
        None,
        description=(
            "The sender's currency. Null for FUNDING, where the "
            "sender side is outside the ledger."
        ),
        examples=["GHS"],
    )
    to_currency: Currency | None = Field(
        None,
        description=(
            "The recipient's currency. Null for WITHDRAWAL, where the "
            "recipient side is outside the ledger."
        ),
        examples=["NGN"],
    )
    from_amount_minor: int | None = Field(
        None,
        ge=1,
        description=(
            "Amount the sender sent, in sender-currency minor units. "
            "Null for FUNDING."
        ),
        examples=[50000],
    )
    to_amount_minor: int | None = Field(
        None,
        ge=1,
        description=(
            "Amount the recipient received, in recipient-currency "
            "minor units. Null for WITHDRAWAL."
        ),
        examples=[5713411],
    )
    fee_minor: int = Field(
        ...,
        ge=0,
        description=(
            "Fee charged by NovaBanq, in the sender's currency. Zero "
            "for FUNDING."
        ),
        examples=[500],
    )
    rate_scaled: int | None = Field(
        None,
        description=(
            "Exchange rate as an integer scaled by LEDGER_RATE_SCALE "
            "(10^6). A rate of 114.268226 is stored as 114268226. "
            "Null for same-currency transactions."
        ),
        examples=[114268226],
    )
    created_at: datetime = Field(
        ...,
        description=(
            "When the ledger committed the transaction, in UTC."
        ),
    )


class TransactionListResponse(BaseModel):
    """One page of transaction summaries.

    ``next_cursor`` is an opaque string the client passes back as the
    ``cursor`` query parameter to fetch the next page. When it's null,
    the caller has reached the end of their history. Do not parse it,
    do not construct it — pass it back verbatim.
    """

    model_config = ConfigDict(frozen=True)

    items: list[TransactionSummary] = Field(
        ...,
        description="The page of transactions, newest first.",
    )
    next_cursor: str | None = Field(
        None,
        description=(
            "Opaque cursor for the next page, or null if there are no "
            "more results. Pass it back as the ``cursor`` query "
            "parameter."
        ),
    )