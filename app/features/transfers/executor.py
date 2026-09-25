"""Transfer executor.

The bridge between the transfers feature and the ledger. Takes the
already-computed amounts (from ``fee_calculator``), the already-resolved
identities (from the service layer), and the already-validated inputs
(from ``validator``), and turns them into a single ``LedgerRequest``
that moves money atomically.

This module contains no validation and no fee math. It assumes every
input has been checked by the caller. It assumes the sender has
sufficient balance (the ledger will re-check inside its transaction —
this is just an optimization boundary). It does not talk to Firestore
or to the currency service. Its only job is: given trusted inputs,
construct the ledger request that the ledger service will execute.

Two shapes of transfer:

    Cross-currency (GHS → NGN):
        5 legs — sender debit, fx_GHS credit, fee_GHS credit,
        fx_NGN debit, recipient credit.

        GHS book: debit 50_500 = credit 50_000 + 500 ✓
        NGN book: debit 5_713_411 = credit 5_713_411 ✓

    Same-currency (GHS → GHS):
        3 legs — sender debit, fee_GHS credit, recipient credit.

        GHS book: debit 50_500 = credit 500 + 50_000 ✓

The FX bridge legs only appear when the sender's and recipient's
currencies differ. A same-currency transfer would otherwise leave the
FX account flat — the debit and credit legs would net to zero — which
the ledger would accept but is wasted work and misleading in the
audit trail.
"""

import logging
from uuid import uuid4

from app.core.constants import (
    LEDGER_RATE_SCALE,
    AccountType,
    Currency,
    EntryDirection,
    SystemAccountPurpose,
    TransactionType,
    system_account_id,
)
from app.features.ledger.schemas import (
    LedgerInstruction,
    LedgerRequest,
)
from app.features.ledger.service import debit_and_credit
from app.features.ledger.schemas import LedgerResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_transfer(
    *,
    idempotency_key: str,
    sender_uid: str,
    recipient_uid: str,
    sender_tag: str,
    sender_name: str,
    recipient_tag: str,
    recipient_name: str,
    from_currency: Currency,
    to_currency: Currency,
    from_amount_minor: int,
    to_amount_minor: int,
    fee_minor: int,
    rate_scaled: int | None,
) -> LedgerResult:
    """Execute a transfer by constructing and running a LedgerRequest.

    Called by the transfers service after validation, fee computation,
    idempotency check, and PIN verification have all passed. Every
    argument here is trusted — this function does not re-validate.

    Args:
        idempotency_key: Client-supplied key. The ledger enforces
            single-use.
        sender_uid: The authenticated caller's uid.
        recipient_uid: The recipient's uid, resolved from their tag.
        sender_tag: Sender's full @tag, for the transaction snapshot.
        sender_name: Sender's display name, for the transaction
            snapshot.
        recipient_tag: Recipient's full @tag, for the transaction
            snapshot.
        recipient_name: Recipient's display name, for the transaction
            snapshot.
        from_currency: Sender's currency.
        to_currency: Recipient's currency. Same as ``from_currency``
            for a same-currency transfer.
        from_amount_minor: Amount the sender sends, in
            ``from_currency`` minor units. Does NOT include the fee.
        to_amount_minor: Amount the recipient receives, in
            ``to_currency`` minor units. Already the result of the FX
            conversion.
        fee_minor: Fee charged, in ``from_currency`` minor units.
        rate_scaled: The exchange rate, scaled by ``LEDGER_RATE_SCALE``
            (rate × 10^6), or ``None`` for a same-currency transfer.

    Returns:
        The ``LedgerResult`` from ``debit_and_credit`` — either a
        fresh settlement or a replay of an earlier one with
        ``duplicate=True``.

    Raises:
        InsufficientBalanceError: Sender's balance cannot cover
            ``from_amount_minor + fee_minor``. Raised by the ledger
            inside its transaction.
        LedgerPreconditionViolatedError: A referenced account (sender,
            recipient, or a system account) does not exist. Raised by
            the ledger inside its transaction.
        LedgerUnbalancedError: The constructed instructions do not
            balance. Should be unreachable — the construction is
            deterministic — but the ledger's own check would catch it.
        LedgerRepositoryError: A Firestore failure, or corrupt stored
            state (e.g. a dangling idempotency record).
    """
    transaction_id = str(uuid4())
    same_currency = from_currency == to_currency

    # Guard: cross-currency transfers must supply a rate, same-currency
    # transfers must not. This mirrors the invariants the ledger's
    # ``TransactionDocument`` and the ``FeeBreakdown`` already enforce,
    # but catching the mismatch here means the error is attributed to
    # the transfers feature (via a clearer stack trace) rather than to
    # the ledger's downstream validation.
    if same_currency and rate_scaled is not None:
        raise ValueError(
            "rate_scaled must be None for a same-currency transfer, "
            f"got {rate_scaled}."
        )
    if not same_currency and rate_scaled is None:
        raise ValueError(
            "rate_scaled is required for a cross-currency transfer."
        )

    instructions = _build_instructions(
        sender_uid=sender_uid,
        recipient_uid=recipient_uid,
        from_currency=from_currency,
        to_currency=to_currency,
        from_amount_minor=from_amount_minor,
        to_amount_minor=to_amount_minor,
        fee_minor=fee_minor,
    )

    metadata = _build_metadata(
        sender_uid=sender_uid,
        recipient_uid=recipient_uid,
        sender_tag=sender_tag,
        sender_name=sender_name,
        recipient_tag=recipient_tag,
        recipient_name=recipient_name,
        from_currency=from_currency,
        to_currency=to_currency,
        from_amount_minor=from_amount_minor,
        to_amount_minor=to_amount_minor,
        fee_minor=fee_minor,
        rate_scaled=rate_scaled,
    )

    request = LedgerRequest(
        transaction_id=transaction_id,
        idempotency_key=idempotency_key,
        transaction_type=TransactionType.TRANSFER,
        instructions=instructions,
        metadata=metadata,
    )

    logger.info(
        "Executing transfer %s: %s %d → %s %d (fee %d).",
        transaction_id,
        from_currency.value,
        from_amount_minor,
        to_currency.value,
        to_amount_minor,
        fee_minor,
    )

    return debit_and_credit(request)


# ---------------------------------------------------------------------------
# Instruction construction
# ---------------------------------------------------------------------------

def _build_instructions(
    *,
    sender_uid: str,
    recipient_uid: str,
    from_currency: Currency,
    to_currency: Currency,
    from_amount_minor: int,
    to_amount_minor: int,
    fee_minor: int,
) -> tuple[LedgerInstruction, ...]:
    """Build the ordered tuple of ledger instructions for a transfer.

    Cross-currency transfers produce 5 legs (sender debit, FX bridge
    both sides, fee credit, recipient credit). Same-currency transfers
    produce 3 legs — the FX bridge legs would net to zero and are
    omitted.

    The order below matches the natural reading order of the transfer:
    what the sender gives up, how it flows through the platform, and
    what the recipient receives. The ledger validates balance per
    currency regardless of order, but a deterministic, readable order
    makes log inspection easier.

    Raises:
        ValueError: If any amount is not strictly positive, or the fee
            is negative. These are caller bugs — the fee calculator
            already guarantees the shape — but the check here means an
            incorrectly-computed amount cannot slip through to the
            ledger.
    """
    if from_amount_minor <= 0:
        raise ValueError(
            f"from_amount_minor must be positive, got {from_amount_minor}."
        )
    if to_amount_minor <= 0:
        raise ValueError(
            f"to_amount_minor must be positive, got {to_amount_minor}."
        )
    if fee_minor < 0:
        raise ValueError(f"fee_minor must be non-negative, got {fee_minor}.")

    sender_total_debit = from_amount_minor + fee_minor
    same_currency = from_currency == to_currency

    instructions: list[LedgerInstruction] = []

    # Leg 1: debit the sender for the send amount plus the fee.
    instructions.append(
        LedgerInstruction(
            account_id=sender_uid,
            account_type=AccountType.USER,
            currency=from_currency,
            direction=EntryDirection.DEBIT,
            amount_minor=sender_total_debit,
        )
    )

    if same_currency:
        # Leg 2: fee to the platform's fee collector.
        instructions.append(
            LedgerInstruction(
                account_id=system_account_id(
                    SystemAccountPurpose.FEE_COLLECTOR,
                    from_currency,
                ),
                account_type=AccountType.SYSTEM,
                currency=from_currency,
                direction=EntryDirection.CREDIT,
                amount_minor=fee_minor,
            )
        )

        # Leg 3: the transfer amount to the recipient.
        instructions.append(
            LedgerInstruction(
                account_id=recipient_uid,
                account_type=AccountType.USER,
                currency=from_currency,
                direction=EntryDirection.CREDIT,
                amount_minor=from_amount_minor,
            )
        )

        return tuple(instructions)

    # Cross-currency: the FX bridge carries the value from one currency
    # book to the other.
    #
    # Leg 2: sender's currency credited to the FX bridge. Balances the
    # GHS (or from-currency) book:
    #   debit sender_total_debit
    #   credit fx_from (from_amount_minor)
    #   credit fee_from (fee_minor)
    instructions.append(
        LedgerInstruction(
            account_id=system_account_id(
                SystemAccountPurpose.FX_BRIDGE,
                from_currency,
            ),
            account_type=AccountType.SYSTEM,
            currency=from_currency,
            direction=EntryDirection.CREDIT,
            amount_minor=from_amount_minor,
        )
    )

    # Leg 3: fee to the platform, in the sender's currency.
    instructions.append(
        LedgerInstruction(
            account_id=system_account_id(
                SystemAccountPurpose.FEE_COLLECTOR,
                from_currency,
            ),
            account_type=AccountType.SYSTEM,
            currency=from_currency,
            direction=EntryDirection.CREDIT,
            amount_minor=fee_minor,
        )
    )

    # Leg 4: FX bridge releases the converted amount in the recipient's
    # currency. This is the debit side of the NGN (or to-currency) book.
    instructions.append(
        LedgerInstruction(
            account_id=system_account_id(
                SystemAccountPurpose.FX_BRIDGE,
                to_currency,
            ),
            account_type=AccountType.SYSTEM,
            currency=to_currency,
            direction=EntryDirection.DEBIT,
            amount_minor=to_amount_minor,
        )
    )

    # Leg 5: credit the recipient.
    instructions.append(
        LedgerInstruction(
            account_id=recipient_uid,
            account_type=AccountType.USER,
            currency=to_currency,
            direction=EntryDirection.CREDIT,
            amount_minor=to_amount_minor,
        )
    )

    return tuple(instructions)


# ---------------------------------------------------------------------------
# Metadata construction
# ---------------------------------------------------------------------------

def _build_metadata(
    *,
    sender_uid: str,
    recipient_uid: str,
    sender_tag: str,
    sender_name: str,
    recipient_tag: str,
    recipient_name: str,
    from_currency: Currency,
    to_currency: Currency,
    from_amount_minor: int,
    to_amount_minor: int,
    fee_minor: int,
    rate_scaled: int | None,
) -> dict[str, object]:
    """Build the metadata dict for the ``LedgerRequest``.

    The required keys are dictated by
    ``_REQUIRED_METADATA_KEYS[TransactionType.TRANSFER]`` in the ledger
    schemas. ``sender_snapshot`` and ``recipient_snapshot`` are optional
    enrichment — they freeze the counterparty's tag and name as they
    were at the moment of the transfer, so a later profile edit never
    rewrites the transaction record.

    ``rate_scaled`` is included only for cross-currency transfers. The
    ledger's own validation rejects a non-``None`` value on a
    same-currency transaction, so passing ``None`` here is mandatory,
    not just idiomatic.
    """
    metadata: dict[str, object] = {
        "sender_uid": sender_uid,
        "recipient_uid": recipient_uid,
        "from_currency": from_currency.value,
        "to_currency": to_currency.value,
        "from_amount_minor": from_amount_minor,
        "to_amount_minor": to_amount_minor,
        "fee_minor": fee_minor,
        "sender_snapshot": {
            "tag": sender_tag,
            "name": sender_name,
        },
        "recipient_snapshot": {
            "tag": recipient_tag,
            "name": recipient_name,
        },
    }

    if rate_scaled is not None:
        metadata["rate_scaled"] = rate_scaled

    return metadata