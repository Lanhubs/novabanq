"""FxRatesAPI client.

Thin HTTP wrapper around FxRatesAPI's ``/latest`` endpoint. This is
the only place in the codebase that talks to the FX vendor. Every
rate the corridors service fetches goes through ``fetch_rate``.

Endpoint contract (verified against a live response):

    GET {base_url}/latest?base={FROM}&currencies={TO}
    Authorization: Bearer {KEY}

    {
      "success": true,
      "timestamp": 1790347620,
      "date": "2026-09-25T14:47:00.000Z",
      "base": "GHS",
      "rates": { "NGN": 114.268230555 }
    }

Design decisions:
    * The API key is sent as an ``Authorization: Bearer`` header, not
      as a query parameter. URLs are logged by ``httpx`` at INFO level
      and by every reverse proxy in front of the app; headers are not.
      Keeping the key out of the URL is the difference between "the
      key can only leak if someone dumps headers" and "the key leaks
      into every access log line".
    * ``Decimal`` from the raw value, not ``float``. The API returns a
      JSON number, which Python parses as a float — a binary value with
      up to 17 significant digits, not the decimal the server actually
      sent. Passing that float straight into ``Decimal()`` carries the
      binary imprecision into the ledger-bound math. Converting via
      ``str()`` first recovers the exact decimal the API intended.
    * Every failure mode is a single exception type. A caller that
      wants to retry or fall back to a cached rate catches
      ``FxRatesClientError`` and gets a clear message; it doesn't need
      to distinguish HTTP errors from parse errors from missing keys.
    * No retries. The corridors service already has a fallback (the
      cached Firestore rate) — retrying here would just delay the
      fallback and burn the free-tier request budget.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import settings
from app.core.constants import Currency, RateSource
from app.infra.fx.schemas import ExchangeRate, FxRatesClientError

logger = logging.getLogger(__name__)

_LATEST_PATH = "/latest"
_REQUEST_TIMEOUT_SECONDS = 10.0


def fetch_rate(
    from_currency: Currency,
    to_currency: Currency,
) -> ExchangeRate:
    """Fetch the current exchange rate between two currencies.

    Args:
        from_currency: The base currency.
        to_currency: The quote currency. Must differ from
            ``from_currency``; a same-currency lookup is a caller bug.

    Returns:
        An ``ExchangeRate`` with ``source=RateSource.FXRATESAPI`` and
        ``fetched_at`` set to the API's timestamp (or now, if the API
        didn't return a parseable one).

    Raises:
        ValueError: If ``from_currency`` and ``to_currency`` are the
            same — caught before any network call.
        FxRatesClientError: On any provider-side failure: network,
            HTTP, malformed JSON, ``success: false``, or a missing
            rate for the requested currency.
    """
    if from_currency is to_currency:
        raise ValueError(
            "Cannot fetch a rate from a currency to itself; "
            f"got {from_currency.value} on both sides."
        )

    base_url, api_key = settings.require_fxrates_config()

    url = f"{base_url.rstrip('/')}{_LATEST_PATH}"
    params = {
        "base": from_currency.value,
        "currencies": to_currency.value,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json",
    }

    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error(
            "FxRatesAPI timed out fetching %s/%s.",
            from_currency.value,
            to_currency.value,
        )
        raise FxRatesClientError(
            "FX provider timed out.", cause=exc
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception(
            "FxRatesAPI request failed for %s/%s.",
            from_currency.value,
            to_currency.value,
        )
        raise FxRatesClientError(
            "FX provider is unreachable.", cause=exc
        ) from exc

    if response.status_code >= 400:
        # FxRatesAPI returns 4xx for bad keys / rate limits, 5xx for
        # outages. Both are provider failures from the caller's side.
        # The response body frequently explains which; log it in full
        # so the cause is visible without rerunning the request.
        logger.error(
            "FxRatesAPI returned HTTP %s for %s/%s: %s",
            response.status_code,
            from_currency.value,
            to_currency.value,
            response.text,
        )
        raise FxRatesClientError(
            f"FX provider returned HTTP {response.status_code}."
        )

    payload = _parse_json(response)
    return _build_exchange_rate(
        payload=payload,
        from_currency=from_currency,
        to_currency=to_currency,
    )


def _parse_json(response: httpx.Response) -> dict[str, Any]:
    """Return the response body as a JSON object.

    Raises:
        FxRatesClientError: If the body is not valid JSON, or is not a
            JSON object (an array, a bare string, ``null``).
    """
    try:
        data = response.json()
    except ValueError as exc:
        raise FxRatesClientError(
            "FX provider returned a non-JSON payload.", cause=exc
        ) from exc

    if not isinstance(data, dict):
        raise FxRatesClientError(
            "FX provider returned an unexpected payload shape."
        )
    return data


def _build_exchange_rate(
    *,
    payload: dict[str, Any],
    from_currency: Currency,
    to_currency: Currency,
) -> ExchangeRate:
    """Validate and normalize a FxRatesAPI ``/latest`` response.

    Raises:
        FxRatesClientError: If ``success`` is not true, the ``rates``
            map is missing or empty, the requested currency isn't
            present, or the value can't be interpreted as a positive
            Decimal.
    """
    if payload.get("success") is not True:
        # The API sometimes returns ``success: false`` with an ``error``
        # object inside an HTTP 200. Surface whatever it said — it's
        # far more useful than a generic "bad payload".
        logger.error(
            "FxRatesAPI reported failure for %s/%s: %s",
            from_currency.value,
            to_currency.value,
            payload,
        )
        raise FxRatesClientError(
            "FX provider returned an unsuccessful response."
        )

    rates = payload.get("rates")
    if not isinstance(rates, dict) or not rates:
        raise FxRatesClientError(
            "FX provider response is missing a rates map."
        )

    raw_rate = rates.get(to_currency.value)
    if raw_rate is None:
        raise FxRatesClientError(
            f"FX provider response has no rate for {to_currency.value}."
        )

    try:
        # str() first: the raw value is a float parsed by httpx, and
        # Decimal(float) would carry the binary representation's
        # imprecision. str(float) gives Python's shortest round-trip
        # representation, which reconstructs the exact decimal the API
        # sent (for the digit counts these vendors use).
        rate = Decimal(str(raw_rate))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FxRatesClientError(
            f"FX provider returned an uninterpretable rate for "
            f"{to_currency.value}: {raw_rate!r}.",
            cause=exc,
        ) from exc

    if not rate.is_finite() or rate <= 0:
        raise FxRatesClientError(
            f"FX provider returned a non-positive rate for "
            f"{to_currency.value}: {rate}."
        )

    fetched_at = _parse_timestamp(payload)

    return ExchangeRate(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
        source=RateSource.FXRATESAPI,
        fetched_at=fetched_at,
    )


def _parse_timestamp(payload: dict[str, Any]) -> datetime:
    """Return a timezone-aware UTC datetime from the API response.

    Prefers the ISO 8601 ``date`` field, which carries a real UTC
    offset. Falls back to the current UTC time if the field is absent,
    malformed, or lacks a UTC offset — the timestamp is only used for
    cache freshness, so "now" is always safe, but every fallback is
    logged so a drifting or misbehaving upstream is visible in ops
    rather than silently swallowed.
    """
    raw_date = payload.get("date")
    if isinstance(raw_date, str):
        try:
            parsed = datetime.fromisoformat(
                raw_date.replace("Z", "+00:00")
            )
        except ValueError:
            logger.warning(
                "FxRatesAPI returned an unparseable date %r; "
                "using current time.",
                raw_date,
            )
        else:
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc)
            logger.warning(
                "FxRatesAPI returned a date %r with no UTC offset; "
                "using current time.",
                raw_date,
            )

    return datetime.now(timezone.utc)