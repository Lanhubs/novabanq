"""FX provider schemas.

Internal data types for the FX layer. These are dataclasses, not
Pydantic models — they never cross an HTTP boundary, they're
constructed by code we control, and they need to be cheap to build.

Two types:

    * ``ExchangeRate`` — the normalized result of a rate lookup. Every
      provider adapter returns one of these, and the corridors service
      stores one on each corridor document.
    * ``FxRatesClientError`` — raised when the provider itself fails.
      Distinct from "this corridor isn't configured" (that's a business
      outcome, raised by the service) and from "the rate is too stale
      to trust" (also raised by the service).

Design decisions:
    * ``rate`` is a ``Decimal``, not a float. The FX rate feeds into
      money math — ``recipient_amount = sender_amount × rate`` — and
      float arithmetic compounds error over multi-leg conversions.
      ``Decimal`` keeps the arithmetic exact until the final rounding
      into minor units.
    * ``fetched_at`` is a timezone-aware UTC datetime, always. The
      cache freshness check compares it against ``datetime.now(
      timezone.utc)``; a naive datetime would raise on that comparison.
    * ``source`` is part of the type. A rate that came from the live
      provider and a rate that was seeded manually have different
      cache-refresh semantics — the service needs to know which is
      which.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.constants import Currency, RateSource

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExchangeRate:
    """A single exchange rate between two currencies.

    Attributes:
        from_currency: The base currency (what you're converting from).
        to_currency: The quote currency (what you're converting to).
        rate: How many units of ``to_currency`` one unit of
            ``from_currency`` buys. E.g. ``from=GHS, to=NGN,
            rate=Decimal("116.50")`` means 1 GHS = 116.50 NGN.
        source: Where this rate came from — see ``RateSource``. Manual
            corridors are never refreshed; provider-backed corridors
            are refreshed once the cache window expires.
        fetched_at: UTC timestamp of when the provider returned this
            rate. Used by the service to decide whether a refresh is
            needed. For manually-seeded corridors this is the moment
            the seed script wrote the document.
    """

    from_currency: Currency
    to_currency: Currency
    rate: Decimal
    source: RateSource
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.from_currency is self.to_currency:
            raise ValueError(
                "ExchangeRate from_currency and to_currency must differ; "
                f"got {self.from_currency.value} on both sides."
            )
        if self.rate <= 0:
            raise ValueError(
                f"ExchangeRate rate must be positive, got {self.rate}."
            )
        if self.fetched_at.tzinfo is None:
            raise ValueError(
                "ExchangeRate fetched_at must be timezone-aware."
            )
        if self.fetched_at.utcoffset() is None:
            # Catches a tzinfo object that returns None from utcoffset,
            # which the is-None check above wouldn't.
            raise ValueError(
                "ExchangeRate fetched_at must carry a real UTC offset."
            )


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class FxRatesClientError(Exception):
    """Raised when the FX provider itself fails.

    This is an infrastructure error, not a business outcome. The
    corridors service decides what to do about it — typically, fall
    back to a cached rate. It never propagates to the client unchanged.

    Common causes:
        * Network timeout talking to FxRatesAPI.
        * FxRatesAPI returned a non-2xx HTTP status.
        * FxRatesAPI returned a payload this adapter cannot interpret
          (missing rate, unexpected shape).
        * FxRatesAPI credentials are invalid or rate-limited.

    Args:
        message: Human-readable description for logs.
        cause: The underlying exception, if any. Chained to
            ``__cause__`` so tracebacks show the full picture, in
            addition to being kept on ``self.cause`` for callers that
            want to inspect it without walking the traceback.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message)


def _rebuild_fx_client_error(
    message: str,
    cause: Exception | None,
) -> FxRatesClientError:
    """Reconstruct an ``FxRatesClientError`` after pickling or copying.

    Why this exists: by default, ``BaseException.__reduce__`` serializes
    an exception as ``(type(self), self.args, self.__dict__)``. That
    happens to preserve the plain ``self.cause`` attribute — it lives in
    ``__dict__`` — but **not** ``self.__cause__``, the dunder Python's
    traceback machinery actually reads for "the above exception was the
    direct cause of the following exception" chaining. ``__cause__`` is
    a special slot, not a ``__dict__`` entry, and default unpickling
    only ever calls ``type(self)(*self.args)`` — i.e.
    ``FxRatesClientError(message)`` with no ``cause`` — before patching
    in the saved ``__dict__``. The ``if cause is not None:
    self.__cause__ = cause`` line in ``__init__`` never gets a chance to
    run, so ``__cause__`` silently comes back as ``None``.

    The fix is to route reconstruction back through the real
    constructor — this function calls ``FxRatesClientError(message,
    cause=cause)`` — so both ``.cause`` and ``.__cause__`` come back
    correctly. ``copy.copy``/``copy.deepcopy`` use the same
    ``__reduce__`` protocol, so this fixes both of them too, not just
    ``pickle``.

    This function has to stay a plain, module-level function — not a
    nested function, a ``staticmethod``, or a lambda. Pickle stores a
    reference to the reconstructor as ``module.qualname`` and
    re-imports it on load, which only works for names reachable at
    module scope.

    Note:
        This only helps if ``cause`` itself is picklable. If a caller
        chains something inherently unpicklable as the cause (an open
        socket, a raw HTTP response object), pickling the resulting
        ``FxRatesClientError`` will still fail — that's an inherent
        limit of chaining arbitrary exceptions, not something this
        override can paper over.

    Args:
        message: The original error message.
        cause: The original chained exception, or ``None``.

    Returns:
        A new ``FxRatesClientError`` with ``.cause`` and ``.__cause__``
        both set to ``cause``, matching the original.
    """
    return FxRatesClientError(message, cause=cause)


# Attach the reduce hook to the class after definition so it can
# reference the module-level rebuild function (which in turn needs
# ``FxRatesClientError`` to already exist — a decorator on the class
# body can't reach a name defined after it). A plain function assigned
# to a class attribute is still found and bound through the normal
# descriptor protocol, so ``some_error.__reduce__()`` works exactly as
# if this had been written as a method inside the class body.
FxRatesClientError.__reduce__ = lambda self: (  # type: ignore[method-assign]
    _rebuild_fx_client_error,
    (self.message, self.cause),
)