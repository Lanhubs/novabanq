"""Ledger schemas.

Internal data types for the ledger module. These are dataclasses, not
Pydantic models — they never cross an HTTP boundary, they are
constructed by code we control, and they need to be cheap to build
inside a Firestore transaction.

The four types fall into three groups:

    * Input    — LedgerInstruction, LedgerRequest
    * Storage  — LedgerEntry, TransactionDocument
    * Output   — LedgerResult

Design decisions:
    * Every numeric field is an integer. The FX rate is stored as
      ``rate_scaled`` (rate × ``LEDGER_RATE_SCALE``), never as a float.
      The ledger is a pure-integer system.
    * ``LedgerRequest.__post_init__`` validates the per-currency
      balancing invariant. An unbalanced request never reaches
      Firestore.
    * Amount validation here is purely structural — every amount must
      be a positive integer. Business policy like minimum transfer
      size is deliberately NOT enforced in this module: the ledger
      doesn't know what a "normal" transfer looks like, only that every
      leg must move a real, positive amount. That policy belongs to the
      transfers service, which calls the ledger.
    * The dataclasses hold ``datetime`` values because that is the
      logical type. When the repository writes to Firestore it
      substitutes ``SERVER_TIMESTAMP`` in the dict it sends — the
      dataclass itself carries the client's clock for local validation.
    * A ``LedgerEntry`` or ``TransactionDocument`` read back from
      Firestore has its raw string fields coerced to enum members by
      the repository before construction. Invalid values raise
      ``ValueError`` at that boundary.
"""

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.constants import (
    LEDGER_MAX_LEGS_PER_TRANSACTION,
    AccountType,
    Currency,
    EntryDirection,
    TransactionStatus,
    TransactionType,
    parse_system_account_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerInstruction:
    """One debit or credit against one account.

    The primitive operation the ledger executes. A cross-currency
    transfer produces several instructions, all of which must appear in
    a single ``LedgerRequest``.

    Attributes:
        account_id: Firebase uid for a USER account, or a system
            account id (``fx_GHS``) for a SYSTEM account.
        account_type: Which collection the account lives in.
        currency: The currency of this instruction.
        direction: DEBIT or CREDIT.
        amount_minor: Positive integer in the smallest currency unit.
            Direction determines the sign.
    """

    account_id: str
    account_type: AccountType
    currency: Currency
    direction: EntryDirection
    amount_minor: int

    def __post_init__(self) -> None:
        if not self.account_id or not self.account_id.strip():
            raise ValueError("account_id cannot be empty.")

        if not isinstance(self.amount_minor, int) or isinstance(
            self.amount_minor, bool
        ):
            raise TypeError(
                "amount_minor must be an int, got "
                f"{type(self.amount_minor).__name__}."
            )
        if self.amount_minor <= 0:
            # Structural only: zero or negative amounts are a caller
            # bug, not a business rule. Minimum transfer size, fee
            # floors, and similar policy live in the transfers service,
            # not here — a fee or FX-bridge leg can legitimately be
            # smaller than any "normal" transfer amount.
            raise ValueError(
                f"amount_minor must be greater than zero, got "
                f"{self.amount_minor}."
            )

        # Account id format must match the declared account type. A uid
        # passed as SYSTEM would route to a missing document; a system
        # id passed as USER would do the same. Catch it here rather
        # than inside a Firestore transaction.
        if self.account_type is AccountType.SYSTEM:
            try:
                parse_system_account_id(self.account_id)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid SYSTEM account_id {self.account_id!r}: {exc}"
                ) from exc
            # TODO: if parse_system_account_id exposes the currency
            # encoded in the id (e.g. "fx_GHS" -> GHS), cross-check it
            # against self.currency here. As written, nothing stops an
            # instruction from declaring a currency that disagrees with
            # its own account id, which would corrupt the per-currency
            # balancing check below without ever raising.


@dataclass(frozen=True)
class LedgerRequest:
    """A complete money-movement operation.

    Attributes:
        transaction_id: A caller-assigned unique id (ULID/UUID). This
            is the document id in the ``transactions`` collection.
        idempotency_key: A client-supplied unique key. The ledger
            rejects a second request with the same key.
        transaction_type: TRANSFER, FUNDING, WITHDRAWAL, or REVERSAL.
        instructions: The debit/credit instructions. Must balance per
            currency — see ``__post_init__``.
        metadata: Operation-specific context (sender uid, recipient
            uid, corridor, ``rate_scaled``, …). Deep-copied on
            construction so the caller cannot mutate the request after
            it is built — including nested values, not just top-level
            keys. The repository further copies it before writing.
    """

    transaction_id: str
    idempotency_key: str
    transaction_type: TransactionType
    instructions: tuple[LedgerInstruction, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transaction_id or not self.transaction_id.strip():
            raise ValueError("transaction_id cannot be empty.")
        if not self.idempotency_key or not self.idempotency_key.strip():
            raise ValueError("idempotency_key cannot be empty.")

        if not self.instructions:
            raise ValueError("instructions cannot be empty.")
        if len(self.instructions) > LEDGER_MAX_LEGS_PER_TRANSACTION:
            raise ValueError(
                f"instructions exceed the maximum of "
                f"{LEDGER_MAX_LEGS_PER_TRANSACTION} legs per transaction."
            )

        # Deep-copy metadata so the frozen dataclass is fully closed
        # off from later mutation by the caller. A shallow dict(...)
        # copy would still share any nested mutable value (a nested
        # dict or list) with the caller's original object.
        object.__setattr__(self, "metadata", copy.deepcopy(self.metadata))

        self._verify_balanced()

    def _verify_balanced(self) -> None:
        """Every currency's debits must equal its credits.

        The balancing rule is per-currency, not global: a GHS→NGN
        transfer balances the GHS book separately from the NGN book,
        with the FX bridge as the link between them. A single global
        sum would be meaningless across different units.
        """
        per_currency_debits: dict[Currency, int] = {}
        per_currency_credits: dict[Currency, int] = {}

        for instruction in self.instructions:
            bucket = (
                per_currency_debits
                if instruction.direction is EntryDirection.DEBIT
                else per_currency_credits
            )
            bucket[instruction.currency] = (
                bucket.get(instruction.currency, 0) + instruction.amount_minor
            )

        currencies = set(per_currency_debits) | set(per_currency_credits)
        for currency in currencies:
            debits = per_currency_debits.get(currency, 0)
            credits = per_currency_credits.get(currency, 0)
            if debits != credits:
                raise ValueError(
                    f"Ledger request is unbalanced in {currency.value}: "
                    f"debits={debits}, credits={credits}."
                )


# ---------------------------------------------------------------------------
# Storage types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerEntry:
    """One row of the immutable ``ledger_entries`` collection.

    Append-only. An entry is never updated or deleted. Corrections are
    made by writing new, offsetting entries.
    """

    entry_id: str
    transaction_id: str
    account_id: str
    account_type: AccountType
    currency: Currency
    direction: EntryDirection
    amount_minor: int
    created_at: datetime


@dataclass(frozen=True)
class TransactionDocument:
    """One row of the ``transactions`` collection.

    Written exactly once, atomically, in the same Firestore transaction
    as its ledger entries — consistent with ``transactions`` being a
    write-once collection and with the single-shot commit model (read
    balances, verify, write everything, commit — all or nothing). A
    transaction that fails to balance or would leave an account
    negative aborts before anything is written, so no
    ``TransactionDocument`` is ever persisted for it.

    In practice, then, every document actually constructed and written
    through this type has ``status=SETTLED``. ``PENDING`` and
    ``FAILED`` remain valid ``TransactionStatus`` values, reserved for
    a possible future two-phase flow (write PENDING first, settle or
    fail it in a second write) that would let a failed attempt leave an
    audit trail. That flow is not implemented here — adopting it later
    would also mean making ``settled_at`` optional again and revisiting
    "write-once."

    ``from_currency``/``from_amount_minor`` and
    ``to_currency``/``to_amount_minor`` are each independently
    optional, because not every ``transaction_type`` has both sides: a
    FUNDING transaction has no ledger-internal source (money enters
    from outside the ledger), and a WITHDRAWAL has no ledger-internal
    destination (money leaves to outside the ledger). A TRANSFER is
    expected to populate both.

    This dataclass deliberately does NOT enforce which combination of
    ``sender_uid`` / ``recipient_uid`` / ``from_*`` / ``to_*`` is
    required for each ``transaction_type`` (e.g. "FUNDING must set
    ``recipient_uid`` and ``to_*``, and leave ``sender_uid``/``from_*``
    None"). That mapping is real business logic that hasn't been
    pinned down for every type — REVERSAL in particular is ambiguous
    (does it carry both sides, or mirror only the side it reverses?).
    Encoding a guess here risks rejecting a legitimate document because
    the guess was wrong. Add that validation once the per-type shape is
    confirmed.

    ``sender_snapshot``/``recipient_snapshot`` carry a small,
    denormalized copy of the counterparty's tag and display name at the
    time of the transaction, so a transaction-history view can render
    "You sent 58,250 NGN to david323.ng" without a second read of a
    profile whose tag or name may have changed since.
    """

    transaction_id: str
    transaction_type: TransactionType
    status: TransactionStatus
    idempotency_key: str
    sender_uid: str | None
    recipient_uid: str | None
    sender_snapshot: dict[str, str] | None
    recipient_snapshot: dict[str, str] | None
    from_currency: Currency | None
    to_currency: Currency | None
    from_amount_minor: int | None
    to_amount_minor: int | None
    fee_minor: int
    rate_scaled: int | None
    created_at: datetime
    settled_at: datetime | None

    def __post_init__(self) -> None:
        if self.status is TransactionStatus.SETTLED:
            if self.settled_at is None:
                raise ValueError(
                    "settled_at is required when status is SETTLED."
                )
            if self.settled_at < self.created_at:
                raise ValueError(
                    "settled_at must not be earlier than created_at."
                )
        elif self.settled_at is not None:
            raise ValueError(
                f"settled_at must be None when status is {self.status.value}."
            )

        if self.from_amount_minor is not None and self.from_amount_minor <= 0:
            raise ValueError("from_amount_minor must be greater than zero.")
        if self.to_amount_minor is not None and self.to_amount_minor <= 0:
            raise ValueError("to_amount_minor must be greater than zero.")
        if self.fee_minor < 0:
            raise ValueError("fee_minor cannot be negative.")

        # The cross-currency / rate_scaled relationship only makes
        # sense when both sides are present — FUNDING and WITHDRAWAL
        # have no FX conversion happening inside the ledger at all, so
        # this check is skipped whenever either side is absent.
        if self.from_currency is not None and self.to_currency is not None:
            cross_currency = self.from_currency != self.to_currency
            if cross_currency and self.rate_scaled is None:
                raise ValueError(
                    "rate_scaled is required for a cross-currency "
                    "transaction."
                )
            if not cross_currency and self.rate_scaled is not None:
                raise ValueError(
                    "rate_scaled must be None when from_currency equals "
                    "to_currency."
                )


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerResult:
    """Returned by ``debit_and_credit``.

    Attributes:
        transaction_id: The transaction the operation belongs to.
        status: SETTLED on a fresh commit, or the recorded status when
            the call was served from the idempotency cache.
        duplicate: True when the request matched an existing
            idempotency key and no new money moved. Callers should
            return the same response they returned the first time.
        entries: The ledger entries produced by this transaction.
        settled_at: When the balance movement committed. Always set —
            a ``LedgerResult`` represents a completed operation, either
            a fresh settle or a replay of one.
    """

    transaction_id: str
    status: TransactionStatus
    duplicate: bool
    entries: tuple[LedgerEntry, ...]
    settled_at: datetime