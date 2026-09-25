"""Currency service.

The public interface of the currency module. One function — ``get_rate``
— returns a usable rate for a currency pair, refreshing it from
FxRatesAPI when the cached value is stale.

The read path is the whole point of this layer:

    1. Read the corridor from Firestore.
    2. If missing, raise ``CorridorUnsupportedError`` — the pair isn't
       configured at all.
    3. If fresh (within ``RATE_CACHE_SECONDS``), return it as-is. No
       API call. This is the common case — most requests hit a warm
       cache.
    4. If stale, try to fetch a live rate. On success, write it back
       to Firestore — preserving the corridor's existing ``fee_bps``,
       not overwriting it with a default — and return the fresh value.
    5. If the live fetch fails and the cached value is still within
       ``RATE_STALE_HARD_LIMIT_SECONDS``, return the cached value with
       a warning log.
    6. If the live fetch fails and the cached value is beyond the hard
       limit, raise ``RateUnavailableError`` — pricing a transfer on
       a rate this old would be dishonest.

Every caller — the transfers service, the seed script, reconciliation —
gets the same behavior through the same function. There is no bypass.
"""

import logging
from datetime import datetime, timezone

from app.core.constants import (
    RATE_CACHE_SECONDS,
    RATE_STALE_HARD_LIMIT_SECONDS,
    Currency,
    ErrorCode,
)
from app.core.exceptions import NovaBanqError
from app.features.currency import repository
from app.infra.fx.client import fetch_rate
from app.infra.fx.schemas import ExchangeRate, FxRatesClientError

logger = logging.getLogger(__name__)

# Default fee applied to a corridor the first time it is created. Once
# a corridor exists, ``_try_refresh`` reads its stored fee and preserves
# it — this default is only used at seed time.
DEFAULT_FEE_BPS = 100  # 1%


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class CorridorUnsupportedError(NovaBanqError):
    """Raised when a currency pair has no configured corridor.

    This is a business outcome — the pair simply isn't supported. It
    never resolves on retry; the operator has to seed the corridor.
    """

    status_code = 422
    code = ErrorCode.CORRIDOR_UNSUPPORTED
    message = "This currency pair is not currently supported."


class RateUnavailableError(NovaBanqError):
    """Raised when no trustworthy rate can be produced.

    The corridor exists, but the provider is unreachable and the
    cached value is beyond ``RATE_STALE_HARD_LIMIT_SECONDS``. Pricing
    a transfer on a value that old would be dishonest; the caller must
    retry once the provider comes back.
    """

    status_code = 502
    code = ErrorCode.RATE_UNAVAILABLE
    message = "Exchange rate is temporarily unavailable. Please try again shortly."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_rate(
    from_currency: Currency,
    to_currency: Currency,
) -> ExchangeRate:
    """Return a usable rate for the given currency pair.

    Args:
        from_currency: The base currency.
        to_currency: The quote currency.

    Returns:
        An ``ExchangeRate`` — either the fresh cached value, a live
        value just fetched and cached, or the cached value being
        served past its freshness window as a fallback.

    Raises:
        CorridorUnsupportedError: If no corridor document exists for
            this pair.
        RateUnavailableError: If the corridor exists, the provider is
            unreachable, and the cached value is beyond the hard
            staleness limit.
    """
    cached = repository.get(from_currency, to_currency)
    if cached is None:
        logger.error(
            "No corridor configured for %s/%s.",
            from_currency.value,
            to_currency.value,
        )
        raise CorridorUnsupportedError()

    age_seconds = _age_seconds(cached.fetched_at)

    if age_seconds < RATE_CACHE_SECONDS:
        # Fresh. No API call.
        return cached

    # Stale — try to refresh.
    refreshed = _try_refresh(from_currency, to_currency)
    if refreshed is not None:
        return refreshed

    # Refresh failed. Fall back to the cached value if it's still
    # within the hard staleness limit.
    if age_seconds < RATE_STALE_HARD_LIMIT_SECONDS:
        logger.warning(
            "FX provider unavailable; serving cached %s/%s rate from "
            "%s (%d seconds old).",
            from_currency.value,
            to_currency.value,
            cached.fetched_at.isoformat(),
            int(age_seconds),
        )
        return cached

    # Too stale to trust.
    logger.error(
        "FX provider unavailable and cached %s/%s rate is beyond the "
        "hard staleness limit (%d seconds old).",
        from_currency.value,
        to_currency.value,
        int(age_seconds),
    )
    raise RateUnavailableError()


def refresh_corridor(
    from_currency: Currency,
    to_currency: Currency,
    *,
    fee_bps: int = DEFAULT_FEE_BPS,
) -> ExchangeRate:
    """Force a refresh of a corridor from the provider.

    Used by the seed script to populate a corridor for the first time,
    and by an admin path if one is ever added. Unlike ``get_rate``,
    this always hits the provider and raises on failure — no cache
    fallback, because the caller explicitly wants a live value.

    On refresh, the corridor's existing ``fee_bps`` is preserved. Only
    pass ``fee_bps`` explicitly to set the fee on a corridor that
    doesn't exist yet, or to change it as a deliberate admin action.

    Args:
        from_currency: The base currency.
        to_currency: The quote currency.
        fee_bps: Fee to store when the corridor does not yet exist, or
            the value to overwrite with if this is a deliberate fee
            change. Defaults to ``DEFAULT_FEE_BPS``.

    Returns:
        The fresh ``ExchangeRate``, already written to Firestore.

    Raises:
        FxRatesClientError: If the provider fails.
        CorridorRepositoryError: On a Firestore write failure.
    """
    rate = fetch_rate(from_currency, to_currency)
    repository.upsert(rate, fee_bps=fee_bps)
    logger.info(
        "Refreshed corridor %s/%s at rate=%s fee_bps=%d.",
        from_currency.value,
        to_currency.value,
        rate.rate,
        fee_bps,
    )
    return rate


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _age_seconds(fetched_at: datetime) -> float:
    """Return how many seconds ago ``fetched_at`` was.

    Normalizes naive datetimes to UTC-aware. The repository already
    guarantees aware datetimes on read, but defending here means the
    arithmetic can never raise if a future code path constructs an
    ``ExchangeRate`` from a slightly different source.
    """
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - fetched_at).total_seconds()


def _try_refresh(
    from_currency: Currency,
    to_currency: Currency,
) -> ExchangeRate | None:
    """Attempt a live refresh, returning None on any provider failure.

    A refresh is best-effort: it should never abort a transfer if the
    cached value can still serve it. Provider failures are logged at
    warning and the caller falls back.

    Preserves the corridor's existing ``fee_bps``. A refresh only
    updates the rate and its timestamp — any operator-customized fee
    stays put. When the corridor doesn't exist yet (first-time seed),
    the default fee is used.

    Firestore write failures are a different matter — they surface
    through the repository as ``CorridorRepositoryError`` and are
    allowed to propagate. A provider call that succeeded but whose
    result cannot be persisted is a state the caller should know
    about, not something to silently swallow.
    """
    try:
        fresh = fetch_rate(from_currency, to_currency)
    except FxRatesClientError as exc:
        logger.warning(
            "FX refresh failed for %s/%s: %s",
            from_currency.value,
            to_currency.value,
            exc,
        )
        return None

    # Preserve the corridor's configured fee if it already exists. A
    # full `set()` in the repository would otherwise reset it to the
    # default, silently repricing every transfer on this corridor.
    stored_fee = repository.get_fee_bps(from_currency, to_currency)
    fee_bps = stored_fee if stored_fee is not None else DEFAULT_FEE_BPS

    repository.upsert(fresh, fee_bps=fee_bps)
    logger.info(
        "Refreshed stale corridor %s/%s to rate=%s fee_bps=%d.",
        from_currency.value,
        to_currency.value,
        fresh.rate,
        fee_bps,
    )
    return fresh