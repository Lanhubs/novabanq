"""Corridor repository.

Data access layer for the ``corridors`` Firestore collection. One
document per directed currency pair — ``GHS_NGN`` and ``NGN_GHS`` are
separate documents with separate rates, not one bidirectional entry.

Document shape:

    corridors/{FROM}_{TO}
    ├── from_currency:  "GHS"
    ├── to_currency:    "NGN"
    ├── rate:           "114.268230555"   (string — see below)
    ├── rate_scaled:    114268230         (integer — rate × LEDGER_RATE_SCALE)
    ├── fee_bps:        100               (basis points, 100 = 1%)
    ├── source:         "fxratesapi"
    ├── fetched_at:     timestamp
    └── updated_at:     timestamp

Why ``rate`` is stored as a string:

    Firestore stores numbers as IEEE 754 doubles. Writing
    ``114.268230555`` as a Firestore number and reading it back returns
    the same binary float Python would have gotten from JSON, with the
    same precision loss. Storing it as a string and parsing to
    ``Decimal`` on read preserves the exact decimal the FX provider
    sent. ``rate_scaled`` is a separate integer field for the ledger.

This module contains no business logic. Deciding when a rate is stale
enough to refresh, and what to do if the provider is down, belongs to
the service layer.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.constants import (
    LEDGER_RATE_SCALE,
    Currency,
    ErrorCode,
    FirestoreCollection,
    RateSource,
)
from app.core.exceptions import NovaBanqError
from app.infra.firestore import collection, document
from app.infra.fx.schemas import ExchangeRate

logger = logging.getLogger(__name__)


class CorridorRepositoryError(NovaBanqError):
    """Raised when the corridor repository cannot complete an operation.

    Wraps Firestore failures into a retryable outcome. A corrupt stored
    document (unparseable rate, unknown currency) is treated the same
    way — the caller retries, and if the corruption persists the error
    log will name the exact document.
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Exchange rate service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Document id
# ---------------------------------------------------------------------------

def _document_id(from_currency: Currency, to_currency: Currency) -> str:
    """Return the canonical corridor document id.

    Format is ``<FROM>_<TO>`` with both currencies uppercase. The
    single source of truth for corridor ids — never construct these
    strings manually, so a caller can't accidentally hit a different
    document than the one this repository reads.
    """
    return f"{from_currency.value}_{to_currency.value}"


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get(
    from_currency: Currency,
    to_currency: Currency,
) -> ExchangeRate | None:
    """Return the stored rate for a currency pair, or None if absent.

    A missing corridor is a normal state — the caller decides whether
    that means "unsupported pair" or "needs to be seeded."

    Args:
        from_currency: The base currency.
        to_currency: The quote currency.

    Returns:
        An ``ExchangeRate`` reconstructed from the stored document, or
        ``None`` if no corridor exists for this pair.

    Raises:
        CorridorRepositoryError: On any Firestore read failure, or if
            the stored document is present but cannot be parsed.
    """
    doc_id = _document_id(from_currency, to_currency)

    try:
        snapshot = document(FirestoreCollection.CORRIDORS, doc_id).get()
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception("Failed to read corridor %s.", doc_id)
        raise CorridorRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    return _exchange_rate_from_dict(data, doc_id)


def exists(from_currency: Currency, to_currency: Currency) -> bool:
    """Return True if a corridor document exists for this pair.

    Cheaper than ``get`` for callers that only need existence — it
    avoids parsing the rate. Still one Firestore read.

    Raises:
        CorridorRepositoryError: On any Firestore read failure.
    """
    doc_id = _document_id(from_currency, to_currency)

    try:
        snapshot = document(FirestoreCollection.CORRIDORS, doc_id).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to check corridor %s.", doc_id)
        raise CorridorRepositoryError() from exc

    return snapshot.exists


def get_fee_bps(
    from_currency: Currency,
    to_currency: Currency,
) -> int | None:
    """Return the stored fee_bps for a corridor, or None if absent.

    Used by the service layer before a rate refresh, so the refresh
    preserves any operator-customized fee instead of overwriting it
    with the module default. Returns None when the corridor doesn't
    exist — the caller will be seeding it, and should use the default.

    Reads the whole document, so this is not free. If it ever becomes
    hot, replace with a Firestore ``select(["fee_bps"])`` field mask.

    Args:
        from_currency: The base currency.
        to_currency: The quote currency.

    Returns:
        The corridor's configured fee in basis points, or ``None`` if
        no corridor exists for this pair.

    Raises:
        CorridorRepositoryError: On any Firestore read failure, or if
            the document exists but has no usable ``fee_bps`` field.
    """
    doc_id = _document_id(from_currency, to_currency)

    try:
        snapshot = document(FirestoreCollection.CORRIDORS, doc_id).get()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read corridor %s for fee.", doc_id)
        raise CorridorRepositoryError() from exc

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    fee = data.get("fee_bps")
    if not isinstance(fee, int) or isinstance(fee, bool) or fee < 0:
        logger.error(
            "Corridor %s holds an invalid fee_bps %r.", doc_id, fee
        )
        raise CorridorRepositoryError()
    return fee


def list_all() -> list[ExchangeRate]:
    """Return every stored corridor.

    Used by the seed script to verify what was written, and by
    reconciliation tooling. Reads the whole collection — fine at this
    scale (6 currencies = 30 directed pairs), callers should not loop
    this in a hot path.

    Malformed documents are logged and skipped rather than aborting
    the whole listing — one corrupt corridor should not hide the other
    twenty-nine.

    Raises:
        CorridorRepositoryError: On any Firestore read failure.
    """
    try:
        snapshots = collection(FirestoreCollection.CORRIDORS).stream()
        raw = [(s.id, s.to_dict() or {}) for s in snapshots]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list corridors.")
        raise CorridorRepositoryError() from exc

    rates: list[ExchangeRate] = []
    for doc_id, data in raw:
        try:
            rates.append(_exchange_rate_from_dict(data, doc_id))
        except CorridorRepositoryError:
            logger.error(
                "Skipping malformed corridor document %s.", doc_id
            )
    return rates


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def upsert(
    rate: ExchangeRate,
    *,
    fee_bps: int,
) -> None:
    """Write or replace the corridor document for this currency pair.

    Idempotent — the document id is ``<FROM>_<TO>``, so a repeated call
    overwrites the previous value. The whole document is written with
    ``set`` (not ``update``) because every field is owned by this
    repository; there is no second writer to protect against.

    Note:
        Because this is a full ``set``, the caller is responsible for
        passing the corridor's existing ``fee_bps`` when the intent is
        to update only the rate. The service layer does this by reading
        the stored fee via ``get_fee_bps`` before calling ``upsert``.

    ``rate_scaled`` is derived here from ``rate.rate``, not passed by
    the caller — one less thing a caller can get wrong, and it keeps
    the two representations in sync by construction.

    Args:
        rate: The ``ExchangeRate`` to persist. Its ``fetched_at`` is
            stored verbatim so cache freshness reflects when the
            provider returned the value, not when we happened to write
            it.
        fee_bps: Fee in basis points (100 = 1%). Callers pass the
            configured fee for this corridor.

    Raises:
        CorridorRepositoryError: On any Firestore write failure.
        ValueError: If ``fee_bps`` is negative.
    """
    if fee_bps < 0:
        raise ValueError(f"fee_bps cannot be negative, got {fee_bps}.")

    doc_id = _document_id(rate.from_currency, rate.to_currency)
    rate_scaled = int(rate.rate * LEDGER_RATE_SCALE)

    payload: dict[str, Any] = {
        "from_currency": rate.from_currency.value,
        "to_currency": rate.to_currency.value,
        "rate": str(rate.rate),
        "rate_scaled": rate_scaled,
        "fee_bps": fee_bps,
        "source": rate.source.value,
        "fetched_at": rate.fetched_at,
        "updated_at": SERVER_TIMESTAMP,
    }

    try:
        document(FirestoreCollection.CORRIDORS, doc_id).set(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to write corridor %s.", doc_id)
        raise CorridorRepositoryError() from exc

    logger.info(
        "Upserted corridor %s rate=%s source=%s fee_bps=%d.",
        doc_id,
        rate.rate,
        rate.source.value,
        fee_bps,
    )


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------

def _exchange_rate_from_dict(
    data: dict[str, Any],
    doc_id: str,
) -> ExchangeRate:
    """Reconstruct an ``ExchangeRate`` from a stored corridor document.

    Coerces the stored string fields back into enum members and parses
    the rate string into a ``Decimal``. Every failure is logged with
    the document id before the generic ``CorridorRepositoryError`` is
    raised, so a corrupt document is easy to find in the logs even
    though the exception itself carries only the generic message.

    Raises:
        CorridorRepositoryError: If any required field is missing or
            cannot be interpreted.
    """
    from_currency_raw = data.get("from_currency")
    to_currency_raw = data.get("to_currency")
    rate_raw = data.get("rate")
    source_raw = data.get("source")
    fetched_at = data.get("fetched_at")

    if from_currency_raw is None or to_currency_raw is None:
        logger.error(
            "Corridor %s is missing from_currency or to_currency.", doc_id
        )
        raise CorridorRepositoryError()
    if rate_raw is None:
        logger.error("Corridor %s is missing rate.", doc_id)
        raise CorridorRepositoryError()
    if source_raw is None:
        logger.error("Corridor %s is missing source.", doc_id)
        raise CorridorRepositoryError()
    if not isinstance(fetched_at, datetime):
        logger.error(
            "Corridor %s has an invalid fetched_at field.", doc_id
        )
        raise CorridorRepositoryError()

    try:
        from_currency = Currency(from_currency_raw)
        to_currency = Currency(to_currency_raw)
    except ValueError as exc:
        logger.exception(
            "Corridor %s holds an unrecognised currency.", doc_id
        )
        raise CorridorRepositoryError() from exc

    try:
        source = RateSource(source_raw)
    except ValueError as exc:
        logger.exception(
            "Corridor %s holds an unrecognised source.", doc_id
        )
        raise CorridorRepositoryError() from exc

    try:
        rate = Decimal(str(rate_raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        logger.exception(
            "Corridor %s holds an unparseable rate.", doc_id
        )
        raise CorridorRepositoryError() from exc

    if not rate.is_finite() or rate <= 0:
        logger.error("Corridor %s holds a non-positive rate.", doc_id)
        raise CorridorRepositoryError()

    # Normalize to UTC-aware. Firestore returns naive datetimes for
    # stored timestamp fields; the ExchangeRate type requires aware.
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    return ExchangeRate(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
        source=source,
        fetched_at=fetched_at,
    )