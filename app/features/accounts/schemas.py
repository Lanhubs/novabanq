"""Account schemas.

HTTP boundary models for the accounts feature. These Pydantic classes
serialize outgoing responses. There are no request models — the
accounts API is read-only, and the account is created on first access
by the service layer.

Design decisions:
    * Balances are returned in two forms: ``balance_minor`` (integer,
      smallest currency unit) and ``balance_display`` (formatted
      string). The frontend displays the string; the integer is for
      arithmetic if the client needs it.
    * ``currency`` is always present and is the user's own currency.
      It never changes after the account is created.
    * No user identity fields are returned here. The account endpoint
      describes money, not the person.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import CURRENCY_MINOR_UNITS, Currency


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_balance(balance_minor: int, currency: str) -> str:
    """Format a minor-unit balance as a human-readable decimal string.

    Currencies with no minor unit (XOF) are rendered as whole numbers.
    All others render with exactly two decimal places. Thousand
    separators are applied so the string is directly displayable.

    Args:
        balance_minor: Integer balance in the smallest currency unit.
        currency: Currency code (e.g. "NGN", "GHS"). Must exist in
            ``CURRENCY_MINOR_UNITS``.

    Returns:
        A display string, e.g. ``"50,000.00"`` for NGN 50000, or
        ``"1,250"`` for XOF 1250.

    Raises:
        ValueError: If the currency has no configured minor unit.
    """
    minor_units = CURRENCY_MINOR_UNITS.get(currency)
    if minor_units is None:
        raise ValueError(f"No minor unit configured for currency '{currency}'.")

    if minor_units == 1:
        # Zero-decimal currency — no fractional part.
        return f"{balance_minor:,}"

    major = balance_minor // minor_units
    remainder = balance_minor % minor_units
    # Multiply by a power of ten so the remainder is expressed in the
    # same number of digits as the minor unit, then zero-pad.
    digits = len(str(minor_units)) - 1
    fractional = str(remainder).zfill(digits)
    return f"{major:,}.{fractional}"


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class AccountResponse(BaseModel):
    """A single account — one user, one currency, one balance."""

    model_config = ConfigDict(frozen=True)

    currency: Currency = Field(
        ...,
        description="The account's currency. Fixed at creation.",
        examples=["NGN"],
    )
    balance_minor: int = Field(
        ...,
        ge=0,
        description=(
            "Balance in the smallest currency unit (kobo, pesewas, etc). "
            "XOF has no minor unit, so the value equals the whole amount."
        ),
        examples=[5000000],
    )
    balance_display: str = Field(
        ...,
        description="Human-readable formatted balance. Display this directly.",
        examples=["50,000.00"],
    )
    updated_at: datetime | None = Field(
        None,
        description=(
            "UTC timestamp of the last balance change. Null on the "
            "response immediately following account creation: the "
            "repository does not re-read the document after creating "
            "it, and Firestore's SERVER_TIMESTAMP sentinel is resolved "
            "server-side — the write commits with the correct "
            "timestamp, but the resolved value is only returned by a "
            "subsequent read. The next call to GET /accounts/me "
            "returns it populated."
        ),
    )


def build_account_response(account: dict[str, Any]) -> AccountResponse:
    """Project a stored account document into the public response shape.

    Kept in the schema module so the presentation logic for formatting
    a balance lives next to the model that carries it. The service
    layer calls this once, after loading the account.

    Args:
        account: A document read from the ``accounts`` collection. Must
            contain ``currency`` and ``balance_minor``.

    Returns:
        A populated ``AccountResponse``.

    Raises:
        ValueError: If the account document is missing required fields,
            or the currency has no configured minor unit.
    """
    currency = account.get("currency")
    balance_minor = account.get("balance_minor")

    if currency is None or balance_minor is None:
        raise ValueError(
            "Account document is missing 'currency' or 'balance_minor'."
        )

    return AccountResponse(
        currency=currency,
        balance_minor=balance_minor,
        balance_display=_format_balance(balance_minor, currency),
        updated_at=account.get("updated_at"),
    )