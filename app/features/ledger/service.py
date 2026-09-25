"""Ledger service.

The public interface of the ledger module. Six functions, of which
only ``debit_and_credit`` writes to Firestore — everything else is
read-only.

This layer is deliberately thin. The heavy lifting — atomicity,
idempotency, double-entry validation, the Firestore transaction
itself — lives in the repository. The service adds three things:

    1. A stable public API that the funding, transfers, and withdrawal
       modules can call without knowing about ``LedgerRequest``
       construction or repository internals.
    2. Audit logging at the correct level. Every money movement is
       logged once, at ``info``, with the transaction id and the
       currency totals — never with amounts per account or any other
       PII.
    3. A post-hoc verification helper for reconciliation and tests.

There is no HTTP route in this module. The ledger is an internal
service. Funding and transfers expose endpoints that call it.
"""

import logging
from typing import Any

from app.core.constants import (
    Currency,
    EntryDirection,
    ErrorCode,
    FirestoreCollection,
    SystemAccountPurpose,
    system_account_id,
)
from app.core.exceptions import NovaBanqError
from app.features.ledger import repository
from app.features.ledger.repository import (
    LedgerRepositoryError,
    LedgerUnbalancedError,
)
from app.features.ledger.schemas import (
    LedgerEntry,
    LedgerInstruction,
    LedgerRequest,
    LedgerResult,
)
from app.infra.firestore import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class TransactionNotFoundError(NovaBanqError):
    """Raised when a caller references a transaction that does not exist."""

    status_code = 404
    code = ErrorCode.TRANSACTION_NOT_FOUND
    message = "Transaction not found."


# ---------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------

def debit_and_credit(request: LedgerRequest) -> LedgerResult:
    """Execute a ledger request atomically.

    This is the only function in the ledger module that moves money.
    Funding, transfers, and withdrawals all build a ``LedgerRequest``
    and call this function. The request's own ``__post_init__``
    validates structure, metadata, and per-currency balance before any
    Firestore call is made.

    Args:
        request: A fully constructed and validated ledger request.

    Returns:
        A ``LedgerResult`` describing the committed transaction, or a
        replay of an earlier call with ``duplicate=True``.

    Raises:
        InsufficientBalanceError: A USER account would go negative.
        LedgerPreconditionViolatedError: A referenced account does not
            exist, or the metadata is missing a required key.
        LedgerUnbalancedError: The instructions fail to balance.
        LedgerRepositoryError: A Firestore failure or corrupt stored
            state.
    """
    result = repository.execute(request)

    if result.duplicate:
        logger.info(
            "Ledger transaction replayed for transaction_id=%s.",
            result.transaction_id,
        )
    else:
        logger.info(
            "Ledger transaction settled for transaction_id=%s; "
            "type=%s, legs=%d.",
            result.transaction_id,
            request.transaction_type.value,
            len(request.instructions),
        )

    return result


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

def get_balance(uid: str) -> int:
    """Return a user's current balance in the smallest currency unit.

    Delegates to the accounts module, which owns the ``accounts``
    collection. The ledger does not read user balances itself except
    inside a transaction, where it must see the document as part of the
    same atomic read set.

    Args:
        uid: Firebase uid of the user.

    Returns:
        The balance in minor units, or 0 if the account does not exist.

    Raises:
        AccountUnavailableError: On any Firestore read failure.
    """
    # Imported here rather than at module top to avoid a circular
    # import: accounts.service imports from ledger in the transfers
    # flow. See the module docstring for the layering rationale.
    from app.features.accounts import service as accounts_service

    return accounts_service.get_balance_minor(uid)


def get_system_balance(
    purpose: SystemAccountPurpose,
    currency: Currency,
) -> int:
    """Return a system account's balance in the smallest currency unit.

    Used by reconciliation and by the demo seed script to assert the
    system accounts start at zero. The ``purpose`` parameter is typed
    as ``SystemAccountPurpose`` so a string cannot be passed in by
    accident and produce an incorrectly formed account id.

    Args:
        purpose: The system account's purpose.
        currency: The currency of the account.

    Returns:
        The balance in minor units, or 0 if the account does not exist.

    Raises:
        LedgerRepositoryError: On any Firestore read failure.
    """
    system_id = system_account_id(purpose, currency)

    db = get_db()
    try:
        snapshot = (
            db.collection(FirestoreCollection.SYSTEM_ACCOUNTS)
            .document(system_id)
            .get()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read system account %s.", system_id)
        raise LedgerRepositoryError() from exc

    if not snapshot.exists:
        return 0

    data = snapshot.to_dict() or {}
    return int(data.get("balance_minor", 0))


def get_entries_for_transaction(
    transaction_id: str,
) -> tuple[LedgerEntry, ...]:
    """Return every ledger entry for a transaction.

    Pass-through to the repository with a lightweight existence check
    so callers can distinguish "no such transaction" from "transaction
    with no entries" (the latter should be impossible, but a caller
    deserves a clear error if the data is corrupt).

    Args:
        transaction_id: The transaction whose entries to fetch.

    Returns:
        A tuple of ``LedgerEntry`` objects.

    Raises:
        TransactionNotFoundError: If no transaction document exists
            with the given id.
        LedgerRepositoryError: On any Firestore read failure.
    """
    if not _transaction_exists(transaction_id):
        raise TransactionNotFoundError()

    return repository.get_entries_for_transaction(transaction_id)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_transaction_balanced(transaction_id: str) -> None:
    """Confirm a persisted transaction's entries net to zero per currency.

    The second line of defense for the double-entry invariant. Primary
    defense runs before the commit (``LedgerRequest.__post_init__``);
    this function is used by reconciliation and tests to confirm that
    the written entries are what the invariant requires.

    Args:
        transaction_id: The transaction to check.

    Raises:
        TransactionNotFoundError: If no transaction exists with that id.
        LedgerUnbalancedError: If any currency's net is not zero.
    """
    entries = get_entries_for_transaction(transaction_id)

    per_currency: dict[str, int] = {}
    for entry in entries:
        delta = (
            entry.amount_minor
            if entry.direction is EntryDirection.CREDIT
            else -entry.amount_minor
        )
        key = entry.currency.value
        per_currency[key] = per_currency.get(key, 0) + delta

    for currency, net in per_currency.items():
        if net != 0:
            raise LedgerUnbalancedError(
                f"Persisted transaction {transaction_id!r} does not "
                f"balance in {currency}: net={net}."
            )


# ---------------------------------------------------------------------------
# Reversal (reserved — not used by the hackathon flow)
# ---------------------------------------------------------------------------

def reverse_transaction(
    original_transaction_id: str,
    *,
    reversal_transaction_id: str,
    idempotency_key: str,
    reason: str,
) -> LedgerResult:
    """Write offsetting entries for a settled transaction.

    Not exercised by the current funding / transfers flow. Reserved for
    dispute resolution and corrections: the original entries are
    immutable, so a reversal is a second transaction whose instructions
    exactly invert the first.

    Args:
        original_transaction_id: The transaction to reverse.
        reversal_transaction_id: A new id for the reversal transaction.
        idempotency_key: A unique key so a retried reversal cannot run
            twice.
        reason: Free-text reason for the reversal. Stored in metadata
            for audit.

    Returns:
        The ``LedgerResult`` for the reversal transaction.

    Raises:
        TransactionNotFoundError: If the original does not exist.
        LedgerRepositoryError: On any Firestore failure, or if the
            original transaction exists but has no ledger entries
            (corrupt stored state).
    """
    from app.core.constants import TransactionType

    original_entries = get_entries_for_transaction(original_transaction_id)
    if not original_entries:
        # get_entries_for_transaction already raises
        # TransactionNotFoundError when the transaction document itself
        # is missing, so reaching here means the transaction exists but
        # has no entries -- corrupt state, not a lookup failure. Don't
        # report it as "not found".
        logger.error(
            "Transaction %s exists but has no ledger entries; "
            "refusing to reverse.",
            original_transaction_id,
        )
        raise LedgerRepositoryError()

    # The reversal is the exact inverse: a DEBIT becomes a CREDIT and
    # vice versa, same account, same currency, same amount.
    inverse_instructions: list[LedgerInstruction] = []
    for entry in original_entries:
        inverse_instructions.append(
            LedgerInstruction(
                account_id=entry.account_id,
                account_type=entry.account_type,
                currency=entry.currency,
                direction=(
                    EntryDirection.CREDIT
                    if entry.direction is EntryDirection.DEBIT
                    else EntryDirection.DEBIT
                ),
                amount_minor=entry.amount_minor,
            )
        )

    # The REVERSAL metadata contract requires the original transaction's
    # uid fields, currencies, amounts, fee, and its own id. Load them
    # from the transactions collection.
    original_meta = _load_original_metadata(original_transaction_id)

    metadata: dict[str, Any] = {
        "sender_uid": original_meta.get("sender_uid"),
        "recipient_uid": original_meta.get("recipient_uid"),
        "from_currency": original_meta.get("from_currency"),
        "to_currency": original_meta.get("to_currency"),
        "from_amount_minor": original_meta.get("from_amount_minor", 0),
        "to_amount_minor": original_meta.get("to_amount_minor", 0),
        "fee_minor": original_meta.get("fee_minor", 0),
        "original_transaction_id": original_transaction_id,
        "reason": reason,
    }
    if original_meta.get("rate_scaled") is not None:
        metadata["rate_scaled"] = original_meta["rate_scaled"]

    request = LedgerRequest(
        transaction_id=reversal_transaction_id,
        idempotency_key=idempotency_key,
        transaction_type=TransactionType.REVERSAL,
        instructions=tuple(inverse_instructions),
        metadata=metadata,
    )

    return debit_and_credit(request)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _transaction_exists(transaction_id: str) -> bool:
    """Return True if a ``transactions`` document exists."""
    db = get_db()
    try:
        snapshot = (
            db.collection(FirestoreCollection.TRANSACTIONS)
            .document(transaction_id)
            .get()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to check existence of transaction_id=%s.",
            transaction_id,
        )
        raise LedgerRepositoryError() from exc
    return snapshot.exists


def _load_original_metadata(transaction_id: str) -> dict[str, Any]:
    """Load the original transaction document for reversal metadata."""
    db = get_db()
    try:
        snapshot = (
            db.collection(FirestoreCollection.TRANSACTIONS)
            .document(transaction_id)
            .get()
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to load original transaction_id=%s for reversal.",
            transaction_id,
        )
        raise LedgerRepositoryError() from exc

    if not snapshot.exists:
        raise TransactionNotFoundError()

    return snapshot.to_dict() or {}