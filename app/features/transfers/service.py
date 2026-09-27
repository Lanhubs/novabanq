"""Transfer service.

Orchestrates the whole transfer flow: quote and execute. Ties
together the validator, the fee calculator, the idempotency module,
the executor, and the accounts and currency services.

Three public entry points:

    * ``quote(...)`` — resolve the recipient, compute amounts, return
      what the user will confirm. Read-only, no money moves.

    * ``execute(...)`` — the immediate-transfer path. Verifies the
      PIN, checks idempotency, and settles through the ledger.

    * ``execute_pre_authorized(...)`` — the deferred-transfer path
      for scheduled transfers. Identical to ``execute()`` except the
      PIN is not verified here; the caller is expected to have
      verified it out-of-band. See the function docstring for the
      full contract.

All three are idempotent from the caller's perspective: a repeated
quote just recomputes with a fresh rate; a repeated execute returns
the original result (via the ledger's idempotency key check).

Check ordering in ``execute`` is deliberate: idempotency is checked
first (a single cheap read, before anything else), then the checks
that need only already-loaded profiles (self-transfer, amount
minimum, corridor support), and only after those pass does the PIN
get verified and the live FX rate get fetched. A request that was
always going to be rejected for an unrelated reason should never cost
the sender a PIN attempt or cost the platform an FX API call first.

This layer contains no HTTP. The router is thin and calls straight
into these functions.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from app.core.constants import (
    LEDGER_RATE_SCALE,
    RATE_LOCK_SECONDS,
    Currency,
    ErrorCode,
)
from app.core.exceptions import NovaBanqError
from app.features.accounts import service as accounts_service
from app.features.currency import service as currency_service
from app.features.notifications import service as notifications_service
from app.features.tags import service as tags_service
from app.features.transfers import (
    executor,
    fee_calculator,
    idempotency,
    repository,
    validator,
)
from app.features.transfers.schemas import (
    QuoteResponse,
    RecipientSummary,
    TransferResponse,
)
from app.features.users import service as users_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class RecipientNotFoundError(NovaBanqError):
    """Raised when a recipient tag does not resolve to any user."""

    status_code = 404
    code = ErrorCode.RECIPIENT_NOT_FOUND
    message = "No user found with that tag."


class DuplicateTransferError(NovaBanqError):
    """Raised when a client retries a transfer under a used key.

    The ledger itself returns the original result on a duplicate
    request (see ``LedgerResult.duplicate``). This error is for the
    path where the service sees an existing transaction under the key
    *before* calling the ledger — the client should treat this as "your
    retry was already processed" and fetch the original result by
    transaction id.
    """

    status_code = 409
    code = ErrorCode.DUPLICATE_TRANSFER
    message = "This transfer has already been processed."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def quote(
    *,
    sender_uid: str,
    recipient_tag: str,
    send_amount_minor: int,
) -> QuoteResponse:
    """Build a quote the frontend shows the sender before confirm.

    Read-only. No money moves. Recomputes everything from scratch on
    every call, so a stale quote that the client held on to is never
    used for the actual transfer — the execute path recalculates with
    the current rate.

    Args:
        sender_uid: The authenticated caller's uid.
        recipient_tag: Normalized recipient tag, resolved to a user.
        send_amount_minor: Amount in the sender's currency, minor
            units.

    Returns:
        A populated ``QuoteResponse``.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        CorridorUnsupportedError: If the sender's and recipient's
            currencies have no configured corridor.
        RateUnavailableError: If no trustworthy rate is available.
    """
    sender_profile = users_service.get_profile(sender_uid)
    recipient_profile = _resolve_recipient(recipient_tag)

    validator.validate_quote(
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        send_amount_minor=send_amount_minor,
        recipient_tag=recipient_tag,
    )

    from_currency = Currency(sender_profile["currency"])
    to_currency = Currency(recipient_profile["currency"])

    breakdown = _build_breakdown(
        send_amount_minor=send_amount_minor,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    quantized_rate = _quantize_rate(breakdown.rate)

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=RATE_LOCK_SECONDS
    )

    return QuoteResponse(
        sender_currency=from_currency,
        recipient=_summarize_recipient(recipient_profile),
        send_amount_minor=breakdown.send_amount_minor,
        fee_minor=breakdown.fee_minor,
        total_debit_minor=breakdown.total_debit_minor,
        receive_amount_minor=breakdown.receive_amount_minor,
        rate=_format_rate(quantized_rate),
        expires_at=expires_at,
    )


def execute(
    *,
    sender_uid: str,
    recipient_tag: str,
    send_amount_minor: int,
    idempotency_key: str,
    pin: str,
) -> TransferResponse:
    """Execute an immediate transfer and return the settled result.

    The PIN is verified here, against the sender's stored hash, using
    the same lockout policy as the standalone ``verify_pin`` endpoint.
    A failed PIN raises ``PinInvalidError`` / ``PinLockedError`` from
    the users service — the same errors the frontend already handles
    for the PIN-verify endpoint.

    See the module docstring for why the checks below run in this
    specific order.

    Args:
        sender_uid: The authenticated caller's uid.
        recipient_tag: Normalized recipient tag.
        send_amount_minor: Amount in the sender's currency, minor
            units.
        idempotency_key: Client-generated key for deduplication.
        pin: The PIN the sender entered on the confirm screen.

    Returns:
        A populated ``TransferResponse``.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        DuplicateTransferError: If the idempotency key has been used.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        CorridorUnsupportedError: If the currencies have no configured
            corridor.
        PinInvalidError: If the PIN does not match.
        PinLockedError: If the PIN is currently locked.
        RateUnavailableError: If no trustworthy rate is available.
        InsufficientBalanceError: If the sender's balance cannot cover
            send + fee.
        InvalidIdempotencyKeyError: If the key is malformed.
        LedgerRepositoryError: On a Firestore failure.
    """
    sender_profile, recipient_profile = _load_profiles_for_transfer(
        sender_uid=sender_uid,
        recipient_tag=recipient_tag,
        send_amount_minor=send_amount_minor,
        idempotency_key=idempotency_key,
    )

    # Wrap the PIN verification so a lockout triggers the security
    # notification before the exception propagates. The notification
    # call itself cannot raise — see notifications.service — so the
    # original PinLockedError is guaranteed to reach the router
    # unchanged, even if Brevo is down.
    try:
        users_service.verify_pin_for_uid(sender_uid, pin)
    except users_service.PinLockedError:
        notifications_service.send_pin_lockout(profile=sender_profile)
        raise

    return _settle_transfer(
        sender_uid=sender_uid,
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        recipient_tag=recipient_tag,
        send_amount_minor=send_amount_minor,
        idempotency_key=idempotency_key,
    )


def execute_pre_authorized(
    *,
    sender_uid: str,
    recipient_tag: str,
    send_amount_minor: int,
    idempotency_key: str,
) -> TransferResponse:
    """Execute a transfer whose sender has already been authenticated.

    Identical to ``execute()`` in every way except one: **the PIN is
    not verified here.** The caller is asserting that the sender's
    identity was established out-of-band before this call.

    The intended caller is the scheduled-transfer service. That flow
    verifies the sender's PIN at *scheduling* time — when the user is
    present and can be challenged — and then fires the transfer at
    the scheduled moment, when the PIN no longer exists anywhere and
    cannot be re-verified. By the time this function runs, the
    schedule itself is the authorization: the user, having proved who
    they are, asked the platform to send money at a specific future
    time.

    **Any future caller of this function assumes the same
    responsibility**: establishing that the sender authorized the
    transfer through some means the platform trusts. A caller that
    skips authentication entirely — e.g. a route that maps directly
    to this function without a PIN check — would let anyone drain any
    account. Do not add callers without a corresponding
    authorization story.

    The docstring is the contract. There is no runtime check that
    can distinguish "the scheduler, which legitimately pre-authorized
    this" from "a new endpoint that forgot the PIN check." Keep the
    trust boundary at the caller, and keep the list of callers short.

    Args:
        sender_uid: The uid of the sender whose identity was
            established out-of-band.
        recipient_tag: Normalized recipient tag.
        send_amount_minor: Amount in the sender's currency, minor
            units.
        idempotency_key: Caller-generated key for deduplication. For
            scheduled transfers, this is derived deterministically
            from the scheduled-transfer id so that a retry of the
            same scheduled execution cannot settle twice.

    Returns:
        A populated ``TransferResponse``.

    Raises:
        UserNotFoundError: If the sender has no profile.
        RecipientNotFoundError: If the recipient tag resolves to no
            user.
        DuplicateTransferError: If the idempotency key has been used.
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        CorridorUnsupportedError: If the currencies have no configured
            corridor.
        RateUnavailableError: If no trustworthy rate is available.
        InsufficientBalanceError: If the sender's balance cannot cover
            send + fee.
        InvalidIdempotencyKeyError: If the key is malformed.
        LedgerRepositoryError: On a Firestore failure.
    """
    sender_profile, recipient_profile = _load_profiles_for_transfer(
        sender_uid=sender_uid,
        recipient_tag=recipient_tag,
        send_amount_minor=send_amount_minor,
        idempotency_key=idempotency_key,
    )

    return _settle_transfer(
        sender_uid=sender_uid,
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        recipient_tag=recipient_tag,
        send_amount_minor=send_amount_minor,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Shared pre-flight checks
# ---------------------------------------------------------------------------

def _load_profiles_for_transfer(
    *,
    sender_uid: str,
    recipient_tag: str,
    send_amount_minor: int,
    idempotency_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the idempotency and pre-flight checks shared by both paths.

    Returns the two loaded profiles. The checks run in this order on
    purpose — see the module docstring:

        1. Idempotency key format.
        2. Idempotency key already used?
        3. Load sender and recipient profiles.
        4. Cheap validators (self-transfer, amount minimum, corridor).

    Both public entry points call this and then diverge only on
    whether the PIN is verified.
    """
    idempotency.validate_key(idempotency_key)

    # Checked first, before any other work: a retry of an
    # already-settled transfer should never cost the sender a PIN
    # attempt or the platform an FX lookup on its way to being told
    # "already processed."
    existing = repository.get_by_idempotency_key(idempotency_key)
    if existing is not None:
        raise DuplicateTransferError()

    sender_profile = users_service.get_profile(sender_uid)
    recipient_profile = _resolve_recipient(recipient_tag)

    # Self-transfer, amount-minimum, and corridor-support need nothing
    # beyond the two profiles already loaded. Run them before any
    # further work, so a request that was always going to fail for one
    # of these reasons doesn't also make the sender spend a real PIN
    # attempt first.
    validator.validate_quote(
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        send_amount_minor=send_amount_minor,
        recipient_tag=recipient_tag,
    )

    return sender_profile, recipient_profile


# ---------------------------------------------------------------------------
# Shared settlement
# ---------------------------------------------------------------------------

def _settle_transfer(
    *,
    sender_uid: str,
    sender_profile: dict[str, Any],
    recipient_profile: dict[str, Any],
    recipient_tag: str,
    send_amount_minor: int,
    idempotency_key: str,
) -> TransferResponse:
    """Settle a transfer through the ledger and notify both parties.

    The single place the actual money movement happens for both
    immediate and scheduled transfers. Takes already-loaded profiles
    so the caller has already run ``_load_profiles_for_transfer``.

    Whether the sender's PIN was verified is a decision the caller
    makes; this function does not know or care. That keeps the PIN
    concern at the entry points where the authorization context is
    known, and this shared body purely about the mechanics of
    moving money.

    Args:
        sender_uid: The sender's uid.
        sender_profile: The sender's loaded profile.
        recipient_profile: The recipient's loaded profile.
        recipient_tag: The normalized recipient tag (needed for the
            executor's snapshot).
        send_amount_minor: Amount in the sender's currency, minor
            units.
        idempotency_key: Key for deduplication at the ledger level.

    Returns:
        A populated ``TransferResponse``.

    Raises:
        InsufficientBalanceError: If the sender's balance cannot cover
            send + fee.
        RateUnavailableError: If no trustworthy rate is available.
        LedgerRepositoryError: On a Firestore failure.
        CorridorUnsupportedError: If the currencies have no configured
            corridor.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        SelfTransferError: If sender and recipient are the same user.
    """
    from_currency = Currency(sender_profile["currency"])
    to_currency = Currency(recipient_profile["currency"])

    breakdown = _build_breakdown(
        send_amount_minor=send_amount_minor,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    quantized_rate = _quantize_rate(breakdown.rate)

    sender_balance = accounts_service.get_balance_minor(sender_uid)

    # Re-runs the same quote-time checks (cheap — no new I/O) and adds
    # the balance check, which does need the freshly computed
    # breakdown.
    validator.validate_execute(
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        sender_balance_minor=sender_balance,
        send_amount_minor=send_amount_minor,
        total_debit_minor=breakdown.total_debit_minor,
    )

    result = executor.execute_transfer(
        idempotency_key=idempotency_key,
        sender_uid=sender_uid,
        recipient_uid=recipient_profile["uid"],
        sender_tag=_sender_tag(sender_profile),
        sender_name=_display_name(sender_profile),
        recipient_tag=recipient_tag,
        recipient_name=_display_name(recipient_profile),
        from_currency=from_currency,
        to_currency=to_currency,
        from_amount_minor=breakdown.send_amount_minor,
        to_amount_minor=breakdown.receive_amount_minor,
        fee_minor=breakdown.fee_minor,
        rate_scaled=_rate_scaled(quantized_rate),
    )

    # Notify both parties. Each call swallows its own delivery errors
    # — a Brevo outage must never turn a settled transfer into a
    # failed request. See notifications.service for the guarantee.
    notifications_service.send_transfer_sent(
        sender_profile=sender_profile,
        recipient_display_name=_display_name(recipient_profile),
        recipient_tag=recipient_tag,
        send_amount_minor=breakdown.send_amount_minor,
        fee_minor=breakdown.fee_minor,
        total_debit_minor=breakdown.total_debit_minor,
        sender_currency=from_currency,
        transaction_id=result.transaction_id,
    )
    notifications_service.send_transfer_received(
        recipient_profile=recipient_profile,
        sender_display_name=_display_name(sender_profile),
        sender_tag=_sender_tag(sender_profile),
        receive_amount_minor=breakdown.receive_amount_minor,
        recipient_currency=to_currency,
        transaction_id=result.transaction_id,
    )

    quote_response = QuoteResponse(
        sender_currency=from_currency,
        recipient=_summarize_recipient(recipient_profile),
        send_amount_minor=breakdown.send_amount_minor,
        fee_minor=breakdown.fee_minor,
        total_debit_minor=breakdown.total_debit_minor,
        receive_amount_minor=breakdown.receive_amount_minor,
        rate=_format_rate(quantized_rate),
        expires_at=result.settled_at,
    )

    return TransferResponse(
        transaction_id=result.transaction_id,
        status="SETTLED",
        quote=quote_response,
        settled_at=result.settled_at,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_recipient(recipient_tag: str) -> dict[str, Any]:
    """Resolve a recipient tag to a loaded user profile.

    Raises:
        RecipientNotFoundError: If no user owns the tag.
        UserNotFoundError: If the tag resolves to a uid with no
            profile — should not happen, since tags are written after
            profile creation, but the profile load is the
            authoritative check.
    """
    uid = tags_service.resolve_uid(recipient_tag)
    if uid is None:
        raise RecipientNotFoundError()

    return users_service.get_profile(uid)


def _build_breakdown(
    *,
    send_amount_minor: int,
    from_currency: Currency,
    to_currency: Currency,
) -> fee_calculator.FeeBreakdown:
    """Fetch the rate and fee, then compute the fee breakdown.

    Same-currency transfers skip the FX rate lookup — the rate is
    exactly 1, and getting a corridor for GHS/GHS would be a lookup
    that returns nothing anyway (a currency doesn't have a corridor
    to itself). There's also no corridor to read a fee from in that
    case, so the platform default applies.

    Cross-currency transfers go through the currency service for both
    the rate and the fee. The fee MUST come from
    ``currency_service.get_fee_bps``, not ``DEFAULT_FEE_BPS`` directly
    — the corridor document's ``fee_bps`` is the operator-configured
    fee for that specific pair, and using the platform default
    unconditionally here would silently ignore it, making "tune the
    fee per corridor" a no-op no matter what's stored in Firestore.

    The raw rate returned here may carry more precision than the
    ledger stores — callers must run it through ``_quantize_rate``
    before using it for display or for ``_rate_scaled``, never round
    it independently in two places.
    """
    if from_currency == to_currency:
        rate = Decimal("1")
        fee_bps = currency_service.DEFAULT_FEE_BPS
    else:
        exchange_rate = currency_service.get_rate(from_currency, to_currency)
        rate = exchange_rate.rate
        fee_bps = currency_service.get_fee_bps(from_currency, to_currency)

    return fee_calculator.compute(
        send_amount_minor=send_amount_minor,
        fee_bps=fee_bps,
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
    )


def _summarize_recipient(profile: dict[str, Any]) -> RecipientSummary:
    """Build the recipient summary shown to the sender."""
    return RecipientSummary(
        uid=profile["uid"],
        tag=profile["tag"],
        display_name=_display_name(profile),
        country=profile["country"],
        currency=Currency(profile["currency"]),
    )


def _display_name(profile: dict[str, Any]) -> str:
    """Join the profile's three name fields into a single display name."""
    parts = [
        profile.get("first_name", ""),
        profile.get("middle_name", ""),
        profile.get("last_name", ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _sender_tag(profile: dict[str, Any]) -> str:
    """Return the sender's tag, or their uid if unclaimed.

    Should always be a tag by the time a user sends money — tag claim
    is part of onboarding — but the fallback keeps the snapshot
    non-null if a profile somehow slipped through without one.
    """
    return profile.get("tag") or profile["uid"]


def _quantize_rate(rate: Decimal) -> Decimal:
    """Round a rate to the ledger's actual storage precision.

    This is the single source of truth for what "the rate" is once a
    quote or transfer leaves this service. Both the display string
    (``_format_rate``) and the stored integer (``_rate_scaled``) must
    be derived from this same already-rounded value — computing them
    independently from the raw, higher-precision rate risks the two
    disagreeing by one unit in the last place, which would mean the
    rate shown to the user doesn't exactly match the rate the ledger
    actually applied.
    """
    return rate.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)


def _format_rate(quantized_rate: Decimal) -> str:
    """Format an already-quantized rate (see ``_quantize_rate``) as a string."""
    return str(quantized_rate)


def _rate_scaled(quantized_rate: Decimal) -> int | None:
    """Scale an already-quantized rate (see ``_quantize_rate``) by
    ``LEDGER_RATE_SCALE``, or return None for a same-currency rate of 1.

    The ledger requires ``rate_scaled=None`` for same-currency
    transfers, and a scaled integer for cross-currency. The check
    mirrors the ledger's own validation. Because the input is already
    quantized to exactly six decimal places, multiplying by
    ``LEDGER_RATE_SCALE`` (10^6) always lands on a whole number.
    """
    if quantized_rate == Decimal("1"):
        return None
    return int((quantized_rate * LEDGER_RATE_SCALE).to_integral_value())