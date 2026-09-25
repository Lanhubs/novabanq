"""Ledger repository.

Firestore access for the money-movement engine. Five collections are
touched:

    * ``accounts/{uid}``                  — read and partial-update user balances
    * ``system_accounts/{system_id}``     — read and partial-update system balances
    * ``ledger_entries/{entry_id}``       — append-only writes
    * ``transactions/{transaction_id}``   — single-shot writes
    * ``idempotency_keys/{key}``          — single-shot writes for deduplication

Everything a call to ``execute`` touches happens inside a single
Firestore transaction. Either the whole operation commits, or nothing
does. A partial state cannot occur.

Account balance writes are partial field updates, never ``set``. The
``accounts`` and ``system_accounts`` collections carry fields owned by
other modules (``uid``, ``currency``, ``created_at``); a ``set`` from
this module would wipe them.

Reads and writes inside the transaction:

    * Reads use ``ref.get(transaction=transaction)`` for a single
      document, or ``query.stream(transaction=transaction)`` for a
      query.
    * Writes go through the ``Transaction`` object itself:
      ``transaction.set(ref, data)`` and ``transaction.update(ref, data)``.
      ``DocumentReference.set()``/``update()`` do not accept a
      ``transaction=`` keyword.
    * The transaction is created with ``db.transaction()`` and run by
      calling the ``@firestore.transactional``-decorated function
      directly, passing the transaction as its first argument.

Deployment prerequisite:
    Before any cross-currency transaction can succeed, the
    ``system_accounts`` collection must be seeded with one document per
    ``(purpose, currency)`` pair in use, each with a zero balance.
    Without these, ``execute`` raises ``LedgerPreconditionViolatedError``
    on the first transfer that references a missing system account.

Caller precondition:
    Every USER account referenced by an instruction must already
    exist. Callers (the transfers and funding services) are
    responsible for calling
    ``app.features.accounts.service.get_or_create_for_user(uid)`` for
    each uid before building the ``LedgerRequest``. The ledger does not
    create user accounts.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore
from google.cloud.firestore import (
    SERVER_TIMESTAMP,
    Client,
    DocumentReference,
    DocumentSnapshot,
    Transaction,
)

from app.core.constants import (
    AccountType,
    Currency,
    EntryDirection,
    ErrorCode,
    FirestoreCollection,
    TransactionStatus,
)
from app.core.exceptions import NovaBanqError
from app.features.ledger.schemas import (
    LedgerEntry,
    LedgerInstruction,
    LedgerRequest,
    LedgerResult,
    TransactionDocument,
)
from app.infra.firestore import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class LedgerRepositoryError(NovaBanqError):
    """Raised when the ledger repository cannot complete an operation.

    Wraps low-level Firestore failures into a retryable outcome. The
    caller cannot distinguish which Firestore call failed — the retry
    policy is the same regardless.

    Also raised directly for corrupt stored state (e.g. an idempotency
    record pointing to a missing transaction, or holding an
    unrecognised status), in which case the message is specific and
    propagates unchanged rather than being re-wrapped.
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Ledger service is temporarily unavailable."


class InsufficientBalanceError(NovaBanqError):
    """Raised when a USER account has insufficient funds for a debit.

    This is a business outcome, not an infrastructure failure. The
    frontend shows the user a specific message, not a generic retry.
    """

    status_code = 422
    code = ErrorCode.INSUFFICIENT_BALANCE
    message = "Insufficient balance for this transaction."


class LedgerPreconditionViolatedError(NovaBanqError):
    """Raised when a documented caller precondition is broken.

    Fires when a USER account referenced by an instruction does not
    exist (caller forgot to call ``get_or_create_for_user``), when a
    SYSTEM account has not been seeded, or when transaction metadata is
    missing or invalid in a way the request schema did not catch. This
    is an internal bug in our own code, not the user's request — hence
    500. The distinct code lets logs and dashboards separate it from
    generic internal errors.
    """

    status_code = 500
    code = ErrorCode.LEDGER_PRECONDITION_VIOLATED
    message = "Ledger request precondition violated."


class LedgerUnbalancedError(NovaBanqError):
    """Raised when a request's instructions fail to balance.

    A defense-in-depth check that runs immediately before the writes.
    The primary defense is ``LedgerRequest.__post_init__`` — this only
    fires if that layer was somehow bypassed.
    """

    status_code = 500
    code = ErrorCode.LEDGER_UNBALANCED
    message = "Ledger transaction is unbalanced."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute(request: LedgerRequest) -> LedgerResult:
    """Execute a ledger request atomically.

    All reads and writes happen inside a single Firestore transaction.
    If any step raises, nothing is written and the balance state is
    unchanged.

    The flow inside the transaction:

        0. Idempotency check — read ``idempotency_keys/{key}``. If the
           key exists, return the previously committed result.
        1. Read every referenced account (from ``accounts`` or
           ``system_accounts`` depending on ``account_type``).
        2. Compute new balances. Reject if a USER account would go
           negative.
        3. Re-sum debits and credits per currency as defense-in-depth.
        4. Partial-update account balances with the new values.
        5. Write ``ledger_entries`` documents (one per instruction).
        6. Write the ``transactions`` document.
        7. Write the ``idempotency_keys`` document.

    Args:
        request: The ledger request to execute. Its ``__post_init__``
            has already validated structure, metadata, and balance.

    Returns:
        A ``LedgerResult`` describing the committed transaction, or a
        replay of an earlier one with ``duplicate=True``.

    Raises:
        InsufficientBalanceError: A USER account would go negative.
        LedgerPreconditionViolatedError: A referenced account does not
            exist, or transaction metadata is incomplete or invalid.
        LedgerUnbalancedError: The instructions fail to balance.
        LedgerRepositoryError: A Firestore failure, or corrupt stored
            state (e.g. a dangling idempotency record).
    """
    db: Client = get_db()
    transaction = db.transaction()

    try:
        return _run_transaction(transaction, request)
    except (
        InsufficientBalanceError,
        LedgerPreconditionViolatedError,
        LedgerUnbalancedError,
        LedgerRepositoryError,
    ):
        # Business outcomes and specifically-messaged repository errors
        # propagate unchanged. Re-wrapping LedgerRepositoryError would
        # discard the specific message that explains what was corrupt.
        # The @firestore.transactional decorator has already rolled the
        # transaction back on this path; nothing further to clean up.
        raise
    except Exception as exc:  # noqa: BLE001 — translate any client error
        logger.exception(
            "Ledger transaction failed for transaction_id=%s.",
            request.transaction_id,
        )
        raise LedgerRepositoryError() from exc


def get_entries_for_transaction(
    transaction_id: str,
) -> tuple[LedgerEntry, ...]:
    """Return every ledger entry for a transaction.

    Read-only, outside any transaction. Used by tests, reconciliation,
    and future admin tooling.

    Args:
        transaction_id: The transaction whose entries to fetch.

    Returns:
        A tuple of ``LedgerEntry`` objects. Malformed entries are
        skipped with an error log rather than crashing the caller.

    Raises:
        LedgerRepositoryError: On any Firestore read failure.
    """
    db = get_db()
    try:
        snapshots = (
            db.collection(FirestoreCollection.LEDGER_ENTRIES)
            .where("transaction_id", "==", transaction_id)
            .stream()
        )
        raw_entries = [snapshot.to_dict() or {} for snapshot in snapshots]
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to read ledger entries for transaction_id=%s.",
            transaction_id,
        )
        raise LedgerRepositoryError() from exc

    entries: list[LedgerEntry] = []
    for raw in raw_entries:
        try:
            entries.append(_entry_from_dict(raw))
        except (KeyError, ValueError) as exc:
            logger.error(
                "Skipping malformed ledger entry for transaction_id=%s: %s",
                transaction_id,
                exc,
            )

    return tuple(entries)


# ---------------------------------------------------------------------------
# Transaction body
# ---------------------------------------------------------------------------

@firestore.transactional
def _run_transaction(
    transaction: Transaction,
    request: LedgerRequest,
) -> LedgerResult:
    """The body of the Firestore transaction.

    Decorated with ``@firestore.transactional``. Call it as
    ``_run_transaction(transaction, request)`` after creating
    ``transaction = db.transaction()`` — see ``execute()``. The
    decorator begins the transaction, invokes this function, retries
    the whole thing on a Firestore-level contention error
    (``google.api_core.exceptions.Aborted``), and commits once this
    function returns without raising. Any other exception — including
    every domain error raised below — aborts the transaction
    immediately and propagates unmodified.

    All reads happen before any writes, as Firestore transactions
    require.

    Args:
        transaction: The active Firestore transaction, injected by the
            ``@firestore.transactional`` decorator.
        request: The validated ledger request.

    Returns:
        A ``LedgerResult`` for the committed transaction, or a replay
        when the idempotency key already exists.

    Raises:
        LedgerPreconditionViolatedError: A referenced account is
            missing, or metadata is incomplete or invalid.
        InsufficientBalanceError: A USER account would go negative.
        LedgerUnbalancedError: Instructions fail to balance.
        LedgerRepositoryError: Corrupt stored state.
    """
    db: Client = get_db()

    # Step 0 — idempotency check.
    idempotency_ref = db.collection(
        FirestoreCollection.IDEMPOTENCY_KEYS
    ).document(request.idempotency_key)
    idempotency_snapshot = idempotency_ref.get(transaction=transaction)

    if idempotency_snapshot.exists:
        existing = idempotency_snapshot.to_dict() or {}
        existing_transaction_id = existing.get("transaction_id")
        if not existing_transaction_id:
            raise LedgerRepositoryError(
                "Idempotency record exists but is missing transaction_id."
            )
        return _replay_existing(db, transaction, existing_transaction_id)

    # Step 1 — read every referenced account.
    account_refs: dict[tuple[str, str], DocumentReference] = {}
    account_snapshots: dict[tuple[str, str], DocumentSnapshot] = {}

    for instruction in request.instructions:
        key = (instruction.account_type.value, instruction.account_id)
        if key in account_refs:
            continue  # already read; skip

        if instruction.account_type is AccountType.USER:
            ref = db.collection(FirestoreCollection.ACCOUNTS).document(
                instruction.account_id
            )
        else:
            ref = db.collection(FirestoreCollection.SYSTEM_ACCOUNTS).document(
                instruction.account_id
            )

        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            raise LedgerPreconditionViolatedError(
                f"{instruction.account_type.value} account "
                f"{instruction.account_id!r} does not exist."
            )

        account_refs[key] = ref
        account_snapshots[key] = snapshot

    # Step 2 — compute new balances per account.
    new_balances: dict[tuple[str, str], int] = {}
    for key, snapshot in account_snapshots.items():
        data = snapshot.to_dict() or {}
        new_balances[key] = int(data.get("balance_minor", 0))

    for instruction in request.instructions:
        key = (instruction.account_type.value, instruction.account_id)
        delta = (
            instruction.amount_minor
            if instruction.direction is EntryDirection.CREDIT
            else -instruction.amount_minor
        )
        new_balances[key] += delta

        if (
            instruction.account_type is AccountType.USER
            and new_balances[key] < 0
        ):
            raise InsufficientBalanceError(
                f"USER account {instruction.account_id!r} would go "
                f"negative after this transaction."
            )

    # Step 3 — re-sum debits and credits per currency as
    # defense-in-depth. The primary check ran in
    # ``LedgerRequest.__post_init__``; this confirms nothing bypassed it.
    _assert_balanced(request.instructions)

    # Step 4 — partial-update every account's balance via the
    # transaction object. Never a full `set()`: these documents carry
    # fields owned by other modules.
    for key, new_balance in new_balances.items():
        transaction.update(
            account_refs[key],
            {
                "balance_minor": new_balance,
                "updated_at": SERVER_TIMESTAMP,
            },
        )

    # Step 5 — write the ledger entries.
    now = datetime.now(timezone.utc)
    entries: list[LedgerEntry] = []

    for instruction in request.instructions:
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            transaction_id=request.transaction_id,
            account_id=instruction.account_id,
            account_type=instruction.account_type,
            currency=instruction.currency,
            direction=instruction.direction,
            amount_minor=instruction.amount_minor,
            created_at=now,
        )
        entries.append(entry)

        entry_ref = db.collection(FirestoreCollection.LEDGER_ENTRIES).document(
            entry.entry_id
        )
        transaction.set(entry_ref, _entry_to_dict(entry))

    # Step 6 — write the transaction document.
    tx_doc = _build_transaction_document(request, now)
    tx_ref = db.collection(FirestoreCollection.TRANSACTIONS).document(
        request.transaction_id
    )
    transaction.set(tx_ref, _transaction_to_dict(tx_doc))

    # Step 7 — write the idempotency key.
    transaction.set(
        idempotency_ref,
        {
            "transaction_id": request.transaction_id,
            "created_at": SERVER_TIMESTAMP,
        },
    )

    return LedgerResult(
        transaction_id=request.transaction_id,
        status=tx_doc.status,
        duplicate=False,
        entries=tuple(entries),
        settled_at=now,
    )


def _replay_existing(
    db: Client,
    transaction: Transaction,
    transaction_id: str,
) -> LedgerResult:
    """Return the result of an already-committed transaction.

    Read-only: no writes happen on this path, since the transaction
    was already committed by an earlier call to ``execute``.

    Args:
        db: The Firestore client.
        transaction: The active Firestore transaction.
        transaction_id: The transaction to replay, taken from the
            existing idempotency record.

    Returns:
        A ``LedgerResult`` with ``duplicate=True``. ``status`` is
        always a ``TransactionStatus`` member, matching the type
        returned by the fresh-commit path in ``_run_transaction``.

    Raises:
        LedgerRepositoryError: The idempotency record points to a
            ``transactions`` document that does not exist, or that
            document holds a ``status`` value that isn't a valid
            ``TransactionStatus`` member.
    """
    tx_ref = db.collection(FirestoreCollection.TRANSACTIONS).document(
        transaction_id
    )
    tx_snapshot = tx_ref.get(transaction=transaction)
    if not tx_snapshot.exists:
        raise LedgerRepositoryError(
            f"Idempotency record points to missing transaction "
            f"{transaction_id!r}."
        )

    tx_data = tx_snapshot.to_dict() or {}
    settled_at = tx_data.get("settled_at") or datetime.now(timezone.utc)

    raw_status = tx_data.get("status", TransactionStatus.SETTLED.value)
    try:
        status = TransactionStatus(raw_status)
    except ValueError as exc:
        raise LedgerRepositoryError(
            f"Stored transaction {transaction_id!r} has an unrecognised "
            f"status {raw_status!r}."
        ) from exc

    entries_snapshot = (
        db.collection(FirestoreCollection.LEDGER_ENTRIES)
        .where("transaction_id", "==", transaction_id)
        .stream(transaction=transaction)
    )
    entries: list[LedgerEntry] = []
    for snapshot in entries_snapshot:
        raw = snapshot.to_dict() or {}
        try:
            entries.append(_entry_from_dict(raw))
        except (KeyError, ValueError):
            logger.error(
                "Skipping malformed ledger entry while replaying "
                "transaction_id=%s.",
                transaction_id,
            )

    logger.info(
        "Ledger request replayed for transaction_id=%s.", transaction_id
    )

    return LedgerResult(
        transaction_id=transaction_id,
        status=status,
        duplicate=True,
        entries=tuple(entries),
        settled_at=settled_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_balanced(instructions: tuple[LedgerInstruction, ...]) -> None:
    """Re-sum debits and credits per currency. Raise if unbalanced.

    Args:
        instructions: The instructions to check.

    Raises:
        LedgerUnbalancedError: If any currency's net is not zero.
    """
    per_currency: dict[str, int] = {}
    for instruction in instructions:
        delta = (
            instruction.amount_minor
            if instruction.direction is EntryDirection.CREDIT
            else -instruction.amount_minor
        )
        key = instruction.currency.value
        per_currency[key] = per_currency.get(key, 0) + delta

    for currency, net in per_currency.items():
        if net != 0:
            raise LedgerUnbalancedError(
                f"Currency {currency} nets to {net}, not zero."
            )


def _build_transaction_document(
    request: LedgerRequest,
    now: datetime,
) -> TransactionDocument:
    """Build the ``TransactionDocument`` from the request's metadata.

    The presence of every required key was validated by
    ``LedgerRequest.__post_init__``. This function reads them and
    coerces the currency strings into enum members.

    Args:
        request: The validated ledger request.
        now: A client-side datetime used to satisfy the dataclass's
            own validation. The dict handed to Firestore substitutes
            ``SERVER_TIMESTAMP`` for ``created_at``/``settled_at`` —
            see ``_transaction_to_dict``.

    Returns:
        A populated ``TransactionDocument``.

    Raises:
        LedgerPreconditionViolatedError: A currency is missing or
            unrecognised in metadata, or a cross-currency request
            lacks ``rate_scaled``.
    """
    meta = request.metadata

    from_currency_raw = meta.get("from_currency")
    to_currency_raw = meta.get("to_currency")

    if from_currency_raw is None or to_currency_raw is None:
        raise LedgerPreconditionViolatedError(
            "Transaction metadata must include from_currency and "
            "to_currency."
        )

    try:
        from_currency = Currency(from_currency_raw)
        to_currency = Currency(to_currency_raw)
    except ValueError as exc:
        raise LedgerPreconditionViolatedError(
            f"Transaction metadata contains an unrecognised currency: {exc}."
        ) from exc

    # rate_scaled is required only for cross-currency transactions.
    # Explicit per-branch narrowing so the type checker can prove the
    # value is not None when we call int() on it.
    rate_scaled: int | None
    if from_currency is to_currency:
        rate_scaled = None
    else:
        rate_scaled_raw = meta.get("rate_scaled")
        if rate_scaled_raw is None:
            raise LedgerPreconditionViolatedError(
                "rate_scaled is required for cross-currency transactions."
            )
        rate_scaled = int(rate_scaled_raw)

    return TransactionDocument(
        transaction_id=request.transaction_id,
        transaction_type=request.transaction_type,
        status=TransactionStatus.SETTLED,
        idempotency_key=request.idempotency_key,
        sender_uid=meta.get("sender_uid"),
        recipient_uid=meta.get("recipient_uid"),
        from_currency=from_currency,
        to_currency=to_currency,
        from_amount_minor=int(meta.get("from_amount_minor", 0)),
        to_amount_minor=int(meta.get("to_amount_minor", 0)),
        fee_minor=int(meta.get("fee_minor", 0)),
        rate_scaled=rate_scaled,
        created_at=now,
        settled_at=now,
    )


def _entry_to_dict(entry: LedgerEntry) -> dict[str, Any]:
    """Serialize a ``LedgerEntry`` for a transactional write.

    Note: ``created_at`` is written as ``SERVER_TIMESTAMP`` rather than
    the entry's own ``created_at`` field. The dataclass carries a
    client-side datetime so its own validation can run; the stored
    value is resolved by Firestore on commit and is authoritative.

    Args:
        entry: The entry to serialize.

    Returns:
        A field dict suitable for ``transaction.set(ref, data)``.
    """
    return {
        "entry_id": entry.entry_id,
        "transaction_id": entry.transaction_id,
        "account_id": entry.account_id,
        "account_type": entry.account_type.value,
        "currency": entry.currency.value,
        "direction": entry.direction.value,
        "amount_minor": entry.amount_minor,
        "created_at": SERVER_TIMESTAMP,
    }


def _entry_from_dict(raw: dict[str, Any]) -> LedgerEntry:
    """Deserialize a Firestore document into a ``LedgerEntry``.

    Coerces raw string fields into enum members. Invalid values raise
    ``ValueError``; missing keys raise ``KeyError``. Callers decide
    whether to skip or fail.

    Args:
        raw: A document as returned by ``DocumentSnapshot.to_dict()``.

    Returns:
        A populated ``LedgerEntry``.

    Raises:
        KeyError: A required field is missing.
        ValueError: A field holds an unrecognised enum value.
    """
    return LedgerEntry(
        entry_id=raw["entry_id"],
        transaction_id=raw["transaction_id"],
        account_id=raw["account_id"],
        account_type=AccountType(raw["account_type"]),
        currency=Currency(raw["currency"]),
        direction=EntryDirection(raw["direction"]),
        amount_minor=int(raw["amount_minor"]),
        created_at=raw["created_at"],
    )


def _transaction_to_dict(doc: TransactionDocument) -> dict[str, Any]:
    """Serialize a ``TransactionDocument`` for a transactional write.

    Note: ``created_at`` and ``settled_at`` are written as
    ``SERVER_TIMESTAMP`` rather than the dataclass's datetime fields —
    same rationale as ``_entry_to_dict``.

    Args:
        doc: The transaction document to serialize.

    Returns:
        A field dict suitable for ``transaction.set(ref, data)``.
    """
    return {
        "transaction_id": doc.transaction_id,
        "transaction_type": doc.transaction_type.value,
        "status": doc.status.value,
        "idempotency_key": doc.idempotency_key,
        "sender_uid": doc.sender_uid,
        "recipient_uid": doc.recipient_uid,
        "from_currency": doc.from_currency.value,
        "to_currency": doc.to_currency.value,
        "from_amount_minor": doc.from_amount_minor,
        "to_amount_minor": doc.to_amount_minor,
        "fee_minor": doc.fee_minor,
        "rate_scaled": doc.rate_scaled,
        "created_at": SERVER_TIMESTAMP,
        "settled_at": SERVER_TIMESTAMP,
    }