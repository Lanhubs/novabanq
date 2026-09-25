"""Unit tests for the transfer fee calculator.

Pure arithmetic — no Firestore, no HTTP, no fixtures that touch the
network. Every test constructs a ``FeeBreakdown`` from fixed inputs
and asserts exact integer outputs. If any of these fail, the money
math is wrong and no transfer should ship.

Run:

    pytest tests/test_fee_calculator.py -v
"""

from decimal import Decimal

import pytest

from app.core.constants import Currency
from app.features.transfers.fee_calculator import FeeBreakdown, compute


# ---------------------------------------------------------------------------
# The example from the ledger architecture doc
# ---------------------------------------------------------------------------

def test_ghs_to_ngn_matches_architecture_doc_example() -> None:
    """GHS 500 → NGN at 116.5, 1% fee.

    This is the exact example the ledger architecture doc used to
    describe the five-leg double-entry flow. It is the single case
    that would have caught the missing-division-by-from_units bug —
    the buggy version returned 582,500,000 kobo (100× too much)
    instead of 5,825,000.
    """
    result = compute(
        send_amount_minor=50_000,          # GHS 500.00
        fee_bps=100,                        # 1%
        from_currency=Currency.GHS,
        to_currency=Currency.NGN,
        rate=Decimal("116.5"),
    )

    assert result.send_amount_minor == 50_000       # GHS 500.00
    assert result.fee_minor == 500                   # GHS 5.00
    assert result.total_debit_minor == 50_500        # GHS 505.00
    # 500 GHS × 116.5 = 58,250 NGN = 5,825,000 kobo
    assert result.receive_amount_minor == 5_825_000


# ---------------------------------------------------------------------------
# Same-currency transfers
# ---------------------------------------------------------------------------

def test_same_currency_ghs_to_ghs() -> None:
    """Sender and recipient in the same currency, no conversion."""
    result = compute(
        send_amount_minor=50_000,
        fee_bps=100,
        from_currency=Currency.GHS,
        to_currency=Currency.GHS,
        rate=Decimal("1"),
    )

    assert result.send_amount_minor == 50_000
    assert result.fee_minor == 500
    assert result.total_debit_minor == 50_500
    # Sender entered 500, fee is 5, recipient gets 500. The fee is
    # charged on top of the entered amount, not deducted from it.
    assert result.receive_amount_minor == 50_000


def test_xof_same_currency_no_minor_unit() -> None:
    """XOF has no minor unit; minor and major amounts are identical.

    The source currency being XOF with ``from_units = 1`` is what made
    the missing-division bug invisible in XOF-only testing. This test
    pins the correct behavior anyway so any future refactor that
    accidentally introduces scaling fails here.
    """
    result = compute(
        send_amount_minor=5_000,           # XOF 5000 (no decimals)
        fee_bps=100,
        from_currency=Currency.XOF,
        to_currency=Currency.XOF,
        rate=Decimal("1"),
    )

    assert result.send_amount_minor == 5_000
    assert result.fee_minor == 50
    assert result.total_debit_minor == 5_050
    assert result.receive_amount_minor == 5_000


# ---------------------------------------------------------------------------
# Currency-direction coverage
# ---------------------------------------------------------------------------

def test_normal_currency_to_xof() -> None:
    """A currency with minor units sending into XOF (which has none).

    Every other cross-currency test in this file uses XOF as the
    source (``from_units = 1``), which is exactly the direction that
    let the original missing-division bug hide. This test exercises
    the other direction — ``from_units = 100``, ``to_units = 1`` — so
    the ``to_units`` multiplication path is covered independently of
    ``from_units`` being trivial.
    """
    result = compute(
        send_amount_minor=50_000,          # GHS 500.00
        fee_bps=100,
        from_currency=Currency.GHS,
        to_currency=Currency.XOF,
        rate=Decimal("15.5"),
    )

    assert result.send_amount_minor == 50_000
    assert result.fee_minor == 500
    assert result.total_debit_minor == 50_500
    # 500 GHS × 15.5 = 7,750 XOF. XOF has no minor unit, so this is
    # both the major and minor amount.
    assert result.receive_amount_minor == 7_750


# ---------------------------------------------------------------------------
# Rounding direction
# ---------------------------------------------------------------------------

def test_fee_rounds_up_to_smallest_minor_unit() -> None:
    """A fractional fee rounds up, never down.

    1 bps (0.01%) of 123 minor units = 0.0123 minor units. That rounds
    up to 1, not down to 0. NovaBanq never undercharges.
    """
    result = compute(
        send_amount_minor=123,
        fee_bps=1,
        from_currency=Currency.NGN,
        to_currency=Currency.NGN,
        rate=Decimal("1"),
    )
    assert result.fee_minor == 1


def test_recipient_amount_rounds_down_to_smallest_minor_unit() -> None:
    """A fractional receive amount rounds down, never up.

    5000 XOF (already major units — XOF has no minor unit) at rate
    1.234567 = 6172.835 NGN major units. × 100 kobo/naira =
    617,283.5 kobo exactly — landing precisely on the .5 boundary
    where ROUND_FLOOR and a round-half-up mode would diverge. Floors
    to 617,283, not 617,284. Rounding up here would credit the
    recipient for half a kobo that doesn't correspond to any value the
    sender actually paid for.
    """
    result = compute(
        send_amount_minor=5_000,
        fee_bps=0,                          # no fee, isolate the rounding
        from_currency=Currency.XOF,
        to_currency=Currency.NGN,
        rate=Decimal("1.234567"),
    )
    assert result.receive_amount_minor == 617_283


def test_recipient_amount_truncates_when_fraction_exists() -> None:
    """Force a fractional recipient minor unit; verify it truncates."""
    # 101 XOF at rate 1.00001 = 101.00101 NGN major.
    # × 100 kobo = 10,100.101 kobo. Floors to 10,100.
    result = compute(
        send_amount_minor=101,
        fee_bps=0,
        from_currency=Currency.XOF,
        to_currency=Currency.NGN,
        rate=Decimal("1.00001"),
    )
    assert result.receive_amount_minor == 10_100


# ---------------------------------------------------------------------------
# Zero-fee transfers
# ---------------------------------------------------------------------------

def test_zero_fee_produces_same_total_as_send() -> None:
    """A 0 bps corridor charges nothing."""
    result = compute(
        send_amount_minor=50_000,
        fee_bps=0,
        from_currency=Currency.GHS,
        to_currency=Currency.NGN,
        rate=Decimal("116.5"),
    )
    assert result.fee_minor == 0
    assert result.total_debit_minor == 50_000
    assert result.receive_amount_minor == 5_825_000


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_rejects_zero_send_amount() -> None:
    with pytest.raises(ValueError, match="send_amount_minor must be positive"):
        compute(
            send_amount_minor=0,
            fee_bps=100,
            from_currency=Currency.GHS,
            to_currency=Currency.NGN,
            rate=Decimal("116.5"),
        )


def test_rejects_negative_send_amount() -> None:
    with pytest.raises(ValueError, match="send_amount_minor must be positive"):
        compute(
            send_amount_minor=-1,
            fee_bps=100,
            from_currency=Currency.GHS,
            to_currency=Currency.NGN,
            rate=Decimal("116.5"),
        )


def test_rejects_negative_fee_bps() -> None:
    with pytest.raises(ValueError, match="fee_bps must be non-negative"):
        compute(
            send_amount_minor=50_000,
            fee_bps=-1,
            from_currency=Currency.GHS,
            to_currency=Currency.NGN,
            rate=Decimal("116.5"),
        )


def test_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="rate must be positive"):
        compute(
            send_amount_minor=50_000,
            fee_bps=100,
            from_currency=Currency.GHS,
            to_currency=Currency.NGN,
            rate=Decimal("0"),
        )


def test_rejects_same_currency_with_wrong_rate() -> None:
    """A same-currency transfer must use rate=1.

    A corridor misconfiguration that lets same-currency transfers run
    at a rate other than 1 would silently mint or destroy value — the
    sender's balance decreases by send+fee, the recipient's increases
    by a different number. Reject at construction.
    """
    with pytest.raises(
        ValueError,
        match="rate must be exactly 1 for a same-currency transfer",
    ):
        compute(
            send_amount_minor=50_000,
            fee_bps=100,
            from_currency=Currency.GHS,
            to_currency=Currency.GHS,
            rate=Decimal("1.01"),
        )


# ---------------------------------------------------------------------------
# FeeBreakdown shape
# ---------------------------------------------------------------------------

def test_breakdown_echoes_the_rate_back() -> None:
    """``rate`` on the breakdown is the same Decimal passed in.

    The quote response serializes this. If the calculator ever did
    internal rate adjustment (it doesn't — the corridor's rate already
    accounts for spread), this test would catch the divergence.
    """
    rate = Decimal("114.26823049")
    result = compute(
        send_amount_minor=50_000,
        fee_bps=100,
        from_currency=Currency.GHS,
        to_currency=Currency.NGN,
        rate=rate,
    )
    assert result.rate == rate
    assert isinstance(result, FeeBreakdown)