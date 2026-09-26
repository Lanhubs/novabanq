"""Transfer validation.

Pre-flight checks that run before a quote is computed or a transfer is
executed. Every check here is a business rule that would be a bug if
it fired at a later layer — after the ledger, after the response is
built, after money has moved.

Two entry points:

    * ``validate_quote(...)`` — checks that the sender is allowed to
      request a quote for this recipient and amount. No writes, no
      state change. Cheap to call on every keystroke if the frontend
      ever wants live validation.

    * ``validate_execute(...)`` — calls ``validate_quote`` first, then
      adds the check that only makes sense when actually moving money:
      the sender has sufficient balance.

Both functions raise typed ``NovaBanqError`` subclasses so the global
exception handler serializes them with the correct ``error.code`` and
``status_code`` — the same pattern used everywhere else in this
codebase.

Every function is pure — no Firestore, no HTTP. The caller passes in
already-loaded profiles and balances. This keeps the validator
testable without mocks and keeps the service layer in charge of what
gets loaded.

Corridor support is NOT checked here. The transfers service calls
``currency_service.get_rate`` while computing the fee breakdown, and
that function raises ``CorridorUnsupportedError`` when the pair has no
corridor. Pre-checking in the validator would mean loading the full
corridor list into memory on every request — more I/O for the same
outcome the rate lookup already produces.
"""

import logging
from typing import Any

from app.core.constants import (
    TRANSFER_MIN_AMOUNT_MINOR,
    Currency,
    ErrorCode,
)
from app.core.exceptions import NovaBanqError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class SelfTransferError(NovaBanqError):
    """Raised when the sender and recipient resolve to the same uid."""

    status_code = 422
    code = ErrorCode.SELF_TRANSFER
    message = "You cannot send money to yourself."


class InsufficientBalanceError(NovaBanqError):
    """Raised when the sender's balance cannot cover send + fee.

    Mirrors the ledger's ``InsufficientBalanceError`` by name and code,
    but this one fires at the transfers boundary — before any ledger
    work. A transfer that fails here never opens a Firestore
    transaction.

    The ledger's own check is the authoritative one (it runs inside
    the atomic transaction and cannot be raced). This one exists to
    give the sender a clean rejection without going through the
    ledger's machinery.
    """

    status_code = 422
    code = ErrorCode.INSUFFICIENT_BALANCE
    message = "Insufficient balance for this transfer."


class AmountBelowMinimumError(NovaBanqError):
    """Raised when the send amount is below the platform minimum.

    Should never fire in practice — the request schema already enforces
    ``ge=TRANSFER_MIN_AMOUNT_MINOR``. This check exists so the rule is
    enforced at the service boundary too, not only at the HTTP
    boundary; a future caller that constructs a ``QuoteRequest``
    programmatically (a script, a test, an internal admin tool) hits
    the same protection.
    """

    status_code = 422
    code = ErrorCode.AMOUNT_INVALID
    message = "The amount is below the minimum for a transfer."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_quote(
    *,
    sender_profile: dict[str, Any],
    recipient_profile: dict[str, Any],
    send_amount_minor: int,
    recipient_tag: str,
) -> None:
    """Validate a quote request before the fee calculation runs.

    Checks that don't depend on the sender's balance or on the
    recipient's account existing. A quote is a read — no money moves,
    so we don't need to verify the sender can afford it yet.

    Corridor support is deliberately not checked here — see the module
    docstring.

    Args:
        sender_profile: The authenticated sender's loaded profile.
        recipient_profile: The recipient's loaded profile, resolved
            from the recipient tag.
        send_amount_minor: The amount the sender entered, in the
            sender's minor units.
        recipient_tag: The normalized recipient tag, for log context.

    Raises:
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
    """
    _check_not_self_transfer(sender_profile, recipient_profile)

    if send_amount_minor < TRANSFER_MIN_AMOUNT_MINOR:
        raise AmountBelowMinimumError(
            f"Amount must be at least {TRANSFER_MIN_AMOUNT_MINOR} minor "
            f"units, got {send_amount_minor}."
        )

    # Log context — the tag is the sender's view of the recipient, not
    # the recipient's PII, so it's safe to log at debug. Everything
    # else about the recipient stays out of logs.
    logger.debug(
        "Quote validation passed for %s (amount=%d).",
        recipient_tag,
        send_amount_minor,
    )


def validate_execute(
    *,
    sender_profile: dict[str, Any],
    recipient_profile: dict[str, Any],
    sender_balance_minor: int,
    send_amount_minor: int,
    total_debit_minor: int,
) -> None:
    """Validate an execute request before the ledger is called.

    Runs ``validate_quote``'s checks first, then adds the balance
    check, which only matters when money is about to move. A transfer
    that fails here never opens a Firestore transaction.

    Args:
        sender_profile: The authenticated sender's loaded profile.
        recipient_profile: The recipient's loaded profile.
        sender_balance_minor: The sender's current balance in their
            own currency, read from the accounts collection. The
            authoritative check is still the ledger's — this one is a
            pre-filter.
        send_amount_minor: The amount the sender entered, in the
            sender's minor units.
        total_debit_minor: The send amount plus the fee, in the
            sender's minor units. This is what actually leaves the
            sender's balance.

    Raises:
        SelfTransferError: If sender and recipient are the same user.
        AmountBelowMinimumError: If the amount is below the platform
            minimum.
        InsufficientBalanceError: If the sender's balance cannot cover
            ``total_debit_minor``.
    """
    validate_quote(
        sender_profile=sender_profile,
        recipient_profile=recipient_profile,
        send_amount_minor=send_amount_minor,
        recipient_tag=recipient_profile.get("tag", ""),
    )

    if sender_balance_minor < total_debit_minor:
        logger.warning(
            "Sender uid=%s has insufficient balance: balance=%d, "
            "required=%d.",
            sender_profile.get("uid"),
            sender_balance_minor,
            total_debit_minor,
        )
        raise InsufficientBalanceError()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_not_self_transfer(
    sender_profile: dict[str, Any],
    recipient_profile: dict[str, Any],
) -> None:
    """Reject a transfer where sender and recipient are the same uid.

    A self-transfer is technically valid at the ledger layer — the
    debit and credit both land on the same account and the balances
    net to just the fee. But that's a business-nonsensical operation
    a user should never be able to invoke, so it's rejected here.

    Raises:
        SelfTransferError: If the two profiles share a uid.
    """
    sender_uid = sender_profile.get("uid")
    recipient_uid = recipient_profile.get("uid")

    if sender_uid is None or recipient_uid is None:
        # Both profiles should always have a uid set by the service
        # before this runs. A missing uid is a caller bug, not a user
        # error — fail loudly rather than treating it as "not a self
        # transfer".
        raise ValueError(
            "Both sender and recipient profiles must have a uid set "
            "before validation."
        )

    if sender_uid == recipient_uid:
        raise SelfTransferError()