"""Shared utility functions.

Small, dependency-free helpers used across features. Nothing in this
module reads from or writes to Firestore, and nothing here knows about
HTTP, the ledger, or any feature domain — if a helper needs any of
those, it belongs in the feature that needs it, not here.

Current contents:

    * ``format_amount`` — render a minor-unit integer as a
      human-readable string with the correct currency symbol, decimal
      places, and thousands separators.
    * ``amount_to_minor`` — convert a major-unit ``Decimal`` to an
      integer count of minor units, with exact math and no silent
      truncation.
"""

from decimal import Decimal

from app.core.constants import CURRENCY_DISPLAY_SYMBOL, CURRENCY_MINOR_UNITS, Currency


def format_amount(minor: int, currency: Currency) -> str:
    """Render a minor-unit amount as a display string.

    Produces a string with the currency's symbol, thousands separators,
    and the correct number of decimal places. All formatting decisions
    are driven by two constants: ``CURRENCY_DISPLAY_SYMBOL`` supplies
    the symbol (including any trailing space, e.g. for XOF and ZAR) and
    ``CURRENCY_MINOR_UNITS`` supplies the multiplier that determines
    decimal places. There are no flags, no options, and no per-currency
    special cases in this function.

    The output is intended for human consumption — emails, receipts,
    transaction history. It deliberately differs from
    ``AccountResponse.balance_display``, which is a plain decimal string
    (no symbol, no separators) intended for client-side layout.

    Examples::

        format_amount(5713411, Currency.NGN)  -> "₦57,134.11"
        format_amount(50000,   Currency.GHS)  -> "GH₵500.00"
        format_amount(1023500, Currency.KES)  -> "KSh10,235.00"
        format_amount(49560,   Currency.XOF)  -> "CFA 49,560"
        format_amount(50500,   Currency.ZAR)  -> "R 505.00"
        format_amount(0,       Currency.NGN)  -> "₦0.00"
        format_amount(-50500,  Currency.GHS)  -> "-GH₵505.00"

    Args:
        minor: Amount in minor units of the currency. For XOF, which
            has no minor unit, this is the amount in whole francs.
        currency: The currency the amount is denominated in.

    Returns:
        A display string. Zero, negative, and (theoretically
        impossible) non-whole XOF amounts all render without error.

    Raises:
        KeyError: If ``currency`` is a value not covered by
            ``CURRENCY_DISPLAY_SYMBOL`` or ``CURRENCY_MINOR_UNITS``.
            Unreachable today — both dicts cover every ``Currency``
            member — but stated here rather than claiming the function
            cannot raise at all.
    """
    symbol = CURRENCY_DISPLAY_SYMBOL[currency]
    multiplier = CURRENCY_MINOR_UNITS[currency]

    is_negative = minor < 0
    absolute_minor = abs(minor)

    if multiplier == 1:
        # Zero-decimal currency (XOF). The minor unit *is* the major
        # unit — no division, no fractional part.
        integer_part = str(absolute_minor)
        decimal_part = ""
    else:
        integer_part, remainder = divmod(absolute_minor, multiplier)
        fractional_digits = len(str(multiplier)) - 1
        # Include the leading zeros a plain str(remainder) would drop.
        decimal_part = f"{remainder:0{fractional_digits}d}"

    grouped = _group_thousands(str(integer_part))

    sign = "-" if is_negative else ""
    if decimal_part:
        return f"{sign}{symbol}{grouped}.{decimal_part}"
    return f"{sign}{symbol}{grouped}"


def _group_thousands(digits: str) -> str:
    """Insert commas as thousands separators into a digit string.

    Pure string manipulation — no locale, no float, no dependency.
    Uses ``str.format``'s built-in ``,`` specifier on the integer
    value, which is exact because the value is already a Python int.
    """
    return f"{int(digits):,}"


def amount_to_minor(amount_major: Decimal, currency: Currency) -> int:
    """Convert a major-unit ``Decimal`` amount to an integer minor-unit amount.

    Uses exact ``Decimal`` math — never ``float`` — and refuses amounts
    that carry more precision than the currency's minor unit supports,
    rather than silently truncating a fraction of a cent. A user who
    types ``19.999`` for a two-decimal currency is told the amount is
    invalid; the function does not guess which cent they meant.

    Shared between ``scripts/fund_user.py`` (a CLI tool for crediting
    balances) and the AI intent service (which parses a major-unit
    amount out of a user's natural-language instruction). Kept here so
    there is exactly one major-to-minor conversion in the codebase and
    no chance of the two diverging on rounding.

    Examples::

        amount_to_minor(Decimal("19.99"),  Currency.NGN)  -> 1999
        amount_to_minor(Decimal("5000"),   Currency.GHS)  -> 500000
        amount_to_minor(Decimal("49560"),  Currency.XOF)  -> 49560

    Args:
        amount_major: The amount in major units (e.g. ``Decimal("19.99")``
            for 19.99 naira).
        currency: The currency the amount is denominated in.

    Returns:
        The amount in minor units, as a positive integer.

    Raises:
        ValueError: If the amount is not positive, or carries more
            precision than the currency supports.
    """
    if amount_major <= 0:
        raise ValueError(f"Amount must be positive, got {amount_major}.")

    scale = CURRENCY_MINOR_UNITS[currency]
    exact_minor = amount_major * scale
    amount_minor = int(exact_minor)

    if exact_minor != amount_minor:
        raise ValueError(
            f"{amount_major} has more precision than {currency.value} "
            f"supports ({scale} minor units per major unit)."
        )

    return amount_minor