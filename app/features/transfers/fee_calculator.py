"""Transfer fee calculator.

Computes the fee, the total debit, and the recipient amount for a
transfer — all in integer minor units, using ``Decimal`` for the
intermediate math.

Why this is its own module rather than a function inside the service:
the fee math is the one piece of the transfer flow that has real edge
cases — rounding direction, XOF's lack of minor units, the difference
between "fee is a percentage of what the sender entered" vs "of what
the sender pays". Keeping it isolated makes those decisions easy to
test and easy to change without touching orchestration.

Design decisions:

    * Fee is a percentage of the sender's entered amount, not of the
      total. A 1% fee on a GHS 500 transfer is GHS 5, not GHS 5.05.
      This matches how the sender thinks: "I'm sending 500, and I'm
      paying a small amount on top."

    * Fee rounds UP to the smallest minor unit. A fee of 0.4 kobo
      rounds to 1 kobo, not 0. NovaBanq never undercharges a fee.
      The alternative — round down or round half — either lets users
      shave the fee by crafting amounts, or introduces a fairness
      question ("why did this person pay 4 kobo and I paid 5?").

    * No fee minimum. A GHS 1 transfer with a 1% fee is a 1-pesewa
      fee, which is fine. If the platform ever wants a fee floor,
      it belongs here as an explicit constant, not as an implicit
      round-up.

    * The recipient amount converts the sender's minor-unit amount
      into the sender's major units first (dividing out
      ``from_units``), applies the corridor's stored ``rate`` as a
      ``Decimal`` to that major-unit amount (not to total_debit — the
      fee is separate from what the recipient receives), then converts
      into the recipient's minor units (multiplying by ``to_units``).
      Skipping the first conversion — applying the rate directly to a
      minor-unit amount — silently overpays the recipient by a factor
      of ``from_units`` for any currency that has one.

    * Recipient amount rounds DOWN to the smallest minor unit. The
      rounding direction matters: if NovaBanq has to lose a fraction
      of a kobo on a transfer, it loses it to the recipient side, not
      the sender side. Rounding up would debit the sender for a kobo
      that doesn't correspond to any real value on the receive side.
"""

import logging
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from app.core.constants import (
    CURRENCY_MINOR_UNITS,
    Currency,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class FeeBreakdown:
    """Plain result of a fee computation.

    Not a dataclass because this module never needs equality, hashing,
    or repr — it's consumed immediately by the service and discarded.
    If it ever grows to more than four fields, or needs to be tested
    for equality, promote it to a frozen dataclass.

    Note: ``__slots__`` below fixes which attribute *names* can exist
    on an instance; it does not make the instance immutable. Nothing
    stops a caller from reassigning ``breakdown.fee_minor`` after
    construction. That's acceptable given the object's short,
    single-use lifecycle, but don't rely on it being read-only.
    """

    __slots__ = (
        "send_amount_minor",
        "fee_minor",
        "total_debit_minor",
        "receive_amount_minor",
        "rate",
    )

    def __init__(
        self,
        *,
        send_amount_minor: int,
        fee_minor: int,
        total_debit_minor: int,
        receive_amount_minor: int,
        rate: Decimal,
    ) -> None:
        self.send_amount_minor = send_amount_minor
        self.fee_minor = fee_minor
        self.total_debit_minor = total_debit_minor
        self.receive_amount_minor = receive_amount_minor
        self.rate = rate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute(
    *,
    send_amount_minor: int,
    fee_bps: int,
    from_currency: Currency,
    to_currency: Currency,
    rate: Decimal,
) -> FeeBreakdown:
    """Compute the fee breakdown for a transfer.

    All inputs are trusted — this function does not validate against
    the corridor, does not check the sender has enough balance, and
    does not verify the currencies are supported. Those checks belong
    to the service layer. This function is pure arithmetic.

    Args:
        send_amount_minor: Amount the sender entered, in minor units
            of ``from_currency``. Must be positive.
        fee_bps: Fee in basis points (100 = 1%). Must be non-negative.
        from_currency: Sender's currency — used for minor-unit
            resolution.
        to_currency: Recipient's currency — used for minor-unit
            resolution. For same-currency transfers this equals
            ``from_currency``, and the rate must be exactly 1.
        rate: The exchange rate as a ``Decimal``. 1 unit of
            ``from_currency`` buys ``rate`` units of ``to_currency``.
            For same-currency transfers this must be 1 — enforced
            below, since a corridor misconfiguration that lets a
            same-currency "transfer" apply a nontrivial rate would
            silently mint or destroy value.

    Returns:
        A ``FeeBreakdown`` with all four amounts and the rate echoed
        back.

    Raises:
        ValueError: If any input is invalid — non-positive amount,
            negative fee, non-positive rate, an unrecognised currency,
            or a same-currency pair with a rate other than 1.
    """
    if send_amount_minor <= 0:
        raise ValueError(
            f"send_amount_minor must be positive, got {send_amount_minor}."
        )
    if fee_bps < 0:
        raise ValueError(f"fee_bps must be non-negative, got {fee_bps}.")
    if rate <= 0:
        raise ValueError(f"rate must be positive, got {rate}.")
    if from_currency == to_currency and rate != 1:
        raise ValueError(
            f"rate must be exactly 1 for a same-currency transfer "
            f"({from_currency.value} -> {to_currency.value}), got {rate}."
        )

    from_units = _minor_units_for(from_currency)
    to_units = _minor_units_for(to_currency)

    fee_minor = _compute_fee_minor(send_amount_minor, fee_bps)
    total_debit_minor = send_amount_minor + fee_minor
    receive_amount_minor = _compute_receive_minor(
        send_amount_minor=send_amount_minor,
        rate=rate,
        from_units=from_units,
        to_units=to_units,
    )

    logger.debug(
        "Fee breakdown: send=%d fee=%d total=%d receive=%d "
        "(from_units=%d to_units=%d rate=%s).",
        send_amount_minor,
        fee_minor,
        total_debit_minor,
        receive_amount_minor,
        from_units,
        to_units,
        rate,
    )

    return FeeBreakdown(
        send_amount_minor=send_amount_minor,
        fee_minor=fee_minor,
        total_debit_minor=total_debit_minor,
        receive_amount_minor=receive_amount_minor,
        rate=rate,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _minor_units_for(currency: Currency) -> int:
    """Return the minor-unit multiplier for a currency.

    Raises:
        ValueError: If the currency has no configured minor unit. This
            should never fire in practice — the enum and the map are
            kept in sync — but failing loudly here beats silently
            returning a wrong multiplier.
    """
    units = CURRENCY_MINOR_UNITS.get(currency)
    if units is None:
        raise ValueError(
            f"No minor unit configured for currency {currency.value!r}."
        )
    return units


def _compute_fee_minor(
    send_amount_minor: int,
    fee_bps: int,
) -> int:
    """Compute the fee, rounded up to the smallest minor unit.

    ``fee_bps`` is basis points: 100 bps = 1%, so a fee of X bps is
    ``send_amount × fee_bps / 10_000``. The division is done in
    ``Decimal`` so that fractional results round consistently, and
    ``ROUND_CEILING`` ensures the platform never undercharges by a
    fraction of a minor unit.

    No currency conversion happens here: the fee is charged in the
    sender's own currency, the same denomination as
    ``send_amount_minor``, so this is pure percentage arithmetic.
    """
    raw = Decimal(send_amount_minor) * Decimal(fee_bps) / Decimal(10_000)
    return int(raw.to_integral_value(rounding=ROUND_CEILING))


def _compute_receive_minor(
    *,
    send_amount_minor: int,
    rate: Decimal,
    from_units: int,
    to_units: int,
) -> int:
    """Compute what the recipient gets, rounded down to the minor unit.

    Three steps, in order:
      1. Convert ``send_amount_minor`` (sender's minor units) into the
         sender's major units by dividing by ``from_units``.
      2. Apply ``rate`` to get the recipient's major-unit amount.
      3. Convert into the recipient's minor units by multiplying by
         ``to_units``.

    Step 1 matters: skipping it and applying ``rate`` directly to
    ``send_amount_minor`` overpays the recipient by a factor of
    ``from_units`` for any currency that has one (i.e. every currency
    except XOF). For XOF as the source currency, ``from_units`` is 1,
    so omitting the division happens to have no effect — which is
    exactly why that mistake can pass unnoticed in testing if XOF is
    only ever exercised as the source currency.

    ``ROUND_FLOOR`` on the final step means NovaBanq never credits more
    than the transfer is actually worth — any fractional remainder is
    discarded on the recipient side rather than debited on the sender
    side.
    """
    send_major = Decimal(send_amount_minor) / Decimal(from_units)
    receive_major = send_major * rate
    receive_minor = receive_major * Decimal(to_units)
    return int(receive_minor.to_integral_value(rounding=ROUND_FLOOR))