"""Account schemas.

HTTP boundary models for the accounts feature, plus an internal model
for system accounts used by the ledger.

There are no request models — the accounts API is read-only, and the
account is created on first access by the service layer.

Design decisions:
    * Balances are returned in two forms: ``balance_minor`` (integer,
      smallest currency unit) and ``balance_display`` (formatted
      string). The frontend displays the string; the integer is for
      arithmetic if the client needs it.
    * ``currency`` is always present and is the user's own currency.
      It never changes after the account is created.
    * No user identity fields are returned here. The account endpoint
      describes money, not the person.
    * System accounts (FX bridge, fee collector) have their own model
      because they differ in two ways: their balance may be negative,
      and they carry a ``purpose`` instead of a user. User-facing
      responses never use it.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    CURRENCY_MINOR_UNITS,
    Currency,
    SystemAccountPurpose,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_balance(balance_minor: int, currency: Currency) -> str:
    """Format a minor-unit balance as a human-readable decimal string.

    Currencies with no minor unit (XOF) are rendered as whole numbers.
    All others render with exactly two decimal places. Thousand
    separators are applied so the string is directly displayable.

    Negative balances are formatted with a leading minus sign. This
    only happens for system accounts; user account balances never go
    negative.

    Args:
        balance_minor: Integer balance in the smallest currency unit.
        currency: A ``Currency`` enum member. Typed as the enum rather
            than ``str`` so the shared ``CURRENCY_MINOR_UNITS`` map
            (keyed by ``Currency``) can be looked up without coercion,
            and a bad currency code fails at the type checker rather
            than producing a runtime ``ValueError``.

    Returns:
        A display string, e.g. ``"50,000.00"`` for NGN 50000, or
        ``"1,250"`` for XOF 1250.

    Raises:
        ValueError: If the currency has no configured minor unit.
    """
    minor_units = CURRENCY_MINOR_UNITS.get(currency)
    if minor_units is None:
        raise ValueError(f"No minor unit configured for currency '{currency}'.")

    negative = balance_minor < 0
    magnitude = abs(balance_minor)

    if minor_units == 1:
        # Zero-decimal currency — no fractional part.
        formatted = f"{magnitude:,}"
    else:
        major = magnitude // minor_units
        remainder = magnitude % minor_units
        digits = len(str(minor_units)) - 1
        fractional = str(remainder).zfill(digits)
        formatted = f"{major:,}.{fractional}"

    return f"-{formatted}" if negative else formatted


def _coerce_currency(value: Any) -> Currency:
    """Coerce a stored currency string to a ``Currency`` enum member.

    Firestore stores the currency as a plain string (the enum's
    ``.value`` was written on the way in). This helper does the
    coercion in one place so both response builders fail with a clear
    message on a corrupt stored value instead of a raw ``ValueError``
    from the enum constructor.

    Raises:
        ValueError: If the value is not a recognised ``Currency``.
    """
    try:
        return Currency(value)
    except ValueError as exc:
        raise ValueError(
            f"Stored document holds an unrecognised currency {value!r}."
        ) from exc


# ---------------------------------------------------------------------------
# User account responses
# ---------------------------------------------------------------------------

class AccountResponse(BaseModel):
    """A user's account — one user, one currency, one balance.

    The balance is always non-negative. Every account returned through
    the public API is a user wallet; system clearing accounts are never
    exposed through this model.
    """

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
    """Project a stored user account document into the public response shape.

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
            the balance is negative, or the currency is not recognised.
    """
    currency_raw = account.get("currency")
    balance_minor = account.get("balance_minor")

    if currency_raw is None or balance_minor is None:
        raise ValueError(
            "Account document is missing 'currency' or 'balance_minor'."
        )

    if balance_minor < 0:
        # A user account with a negative balance is a data integrity
        # bug — the ledger must never allow it. Raising here surfaces
        # it immediately rather than returning a poisoned response.
        raise ValueError(
            f"User account balance cannot be negative, got {balance_minor}."
        )

    currency = _coerce_currency(currency_raw)

    return AccountResponse(
        currency=currency,
        balance_minor=balance_minor,
        balance_display=_format_balance(balance_minor, currency),
        updated_at=account.get("updated_at"),
    )


# ---------------------------------------------------------------------------
# System account responses (internal — not exposed via HTTP)
# ---------------------------------------------------------------------------

class SystemAccountResponse(BaseModel):
    """A platform-owned clearing account.

    System accounts differ from user accounts in two ways:

        * Their balance may be negative. An FX bridge account going
          negative is not an error — it records what the platform owes
          pending settlement.
        * They carry a ``purpose`` (FX bridge, fee collector) instead of
          a user identity.

    This model is used by the ledger for reconciliation and by tests.
    It is never returned from a public API route.
    """

    model_config = ConfigDict(frozen=True)

    system_id: str = Field(
        ...,
        description="Canonical system account id, e.g. 'fx_GHS'.",
        examples=["fx_GHS"],
    )
    purpose: SystemAccountPurpose = Field(
        ...,
        description="The account's purpose.",
    )
    currency: Currency = Field(
        ...,
        description="The currency the account holds.",
    )
    balance_minor: int = Field(
        ...,
        description=(
            "Balance in the smallest currency unit. May be negative — "
            "the non-negative invariant applies only to user accounts."
        ),
    )
    balance_display: str = Field(
        ...,
        description="Human-readable formatted balance, with a leading minus if negative.",
        examples=["-500.00"],
    )
    updated_at: datetime | None = Field(
        None,
        description="UTC timestamp of the last balance change.",
    )


def build_system_account_response(
    account: dict[str, Any],
) -> SystemAccountResponse:
    """Project a stored system account document into a typed response.

    Used by the ledger for reconciliation and by tests. Not exposed via
    any HTTP route.

    Args:
        account: A document read from the ``system_accounts``
            collection. Must contain ``system_id``, ``purpose``,
            ``currency``, and ``balance_minor``.

    Returns:
        A populated ``SystemAccountResponse``.

    Raises:
        ValueError: If the document is missing required fields, or the
            currency is not recognised.
    """
    system_id = account.get("system_id")
    purpose = account.get("purpose")
    currency_raw = account.get("currency")
    balance_minor = account.get("balance_minor")

    # Explicit per-field checks so the type checker narrows each
    # variable from `Any | None` to a concrete type for the return
    # statement. A single aggregated `missing` list would not narrow.
    if system_id is None:
        raise ValueError("System account document is missing 'system_id'.")
    if purpose is None:
        raise ValueError("System account document is missing 'purpose'.")
    if currency_raw is None:
        raise ValueError("System account document is missing 'currency'.")
    if balance_minor is None:
        raise ValueError("System account document is missing 'balance_minor'.")

    currency = _coerce_currency(currency_raw)

    return SystemAccountResponse(
        system_id=system_id,
        purpose=purpose,
        currency=currency,
        balance_minor=balance_minor,
        balance_display=_format_balance(balance_minor, currency),
        updated_at=account.get("updated_at"),
    )