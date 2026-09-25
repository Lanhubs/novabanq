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
    * ``LedgerRequest.__post_init__`` validates three things before the
      request can be used:

          1. Structure — non-empty ids, instruction count within the
             configured cap.
          2. Metadata — the keys required for the transaction type are
             present, including the uid fields.
          3. Balance — debits equal credits per currency.

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
    * ``from_currency``/``from_amount_minor`` and ``to_currency``/
      ``to_amount_minor`` are nullable as a pair on
      ``TransactionDocument``. FUNDING has no "from" side and
      WITHDRAWAL has no "to" side — that side's external leg is
      outside the ledger. Each pair is present together or absent
      together; an amount without a currency, or the reverse, is
      never valid.
    * Counterparty identity can be snapshotted, not just referenced.
      ``sender_snapshot`` and ``recipient_snapshot`` freeze a user's
      tag and display name as they were at the moment a transaction
      settled, so a later rename or retag never rewrites how a past
      transaction is displayed. A snapshot is optional enrichment: a
      transaction is fully valid with a uid and no snapshot (the
      frontend falls back to a live profile lookup), but a snapshot
      can never exist without its uid. Avatar is deliberately
      excluded — see ``_SNAPSHOT_KEYS``.
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
# Metadata contract
# ---------------------------------------------------------------------------

# The keys each transaction type must carry in ``LedgerRequest.metadata``.
# The ledger does not know what a "transfer" means semantically — it only
# knows which keys each type promises to carry, the same way it knows
# instructions must balance per currency.
#
# ``rate_scaled`` is deliberately NOT listed here. It is conditionally
# required (only when from_currency != to_currency), so the repository
# validates its presence after reading the two currency fields.
#
# ``sender_snapshot`` / ``recipient_snapshot`` are deliberately NOT
# listed here. They are optional enrichment on ``TransactionDocument``,
# not part of the ledger's required-keys contract — a caller that
# can't produce a snapshot (a failed profile read, a not-yet-updated
# caller) should still be able to move money.
_REQUIRED_METADATA_KEYS: dict[TransactionType, frozenset[str]] = {
    TransactionType.TRANSFER: frozenset({
        "sender_uid",
        "recipient_uid",
        "from_currency",
        "to_currency",
        "from_amount_minor",
        "to_amount_minor",
        "fee_minor",
    }),
    TransactionType.FUNDING: frozenset({
        "recipient_uid",
        "to_currency",
        "to_amount_minor",
        "fee_minor",
    }),
    TransactionType.WITHDRAWAL: frozenset({
        "sender_uid",
        "from_currency",
        "from_amount_minor",
        "fee_minor",
    }),
    TransactionType.REVERSAL: frozenset({
        "sender_uid",
        "recipient_uid",
        "from_currency",
        "to_currency",
        "from_amount_minor",
        "to_amount_minor",
        "fee_minor",
        "original_transaction_id",
    }),
}


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
                _, encoded_currency = parse_system_account_id(self.account_id)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid SYSTEM account_id {self.account_id!r}: {exc}"
                ) from exc

            # The id encodes its currency ("fx_GHS" -> GHS). If the
            # instruction declares a different currency, the mismatch
            # would corrupt the per-currency balancing check in
            # LedgerRequest without ever raising.
            if encoded_currency is not self.currency:
                raise ValueError(
                    f"SYSTEM account_id {self.account_id!r} encodes "
                    f"currency {encoded_currency.value}, but the "
                    f"instruction declares {self.currency.value}."
                )


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
        metadata: Operation-specific context. Must carry the keys
            required by ``transaction_type`` — see
            ``_REQUIRED_METADATA_KEYS``. Deep-copied on construction so
            the caller cannot mutate the request after it is built —
            including nested values, not just top-level keys.
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

        self._verify_metadata()
        self._verify_balanced()

    def _verify_metadata(self) -> None:
        """Every required metadata key for this transaction type must be present.

        The ledger stays generic — it does not know what a TRANSFER
        means. But it does know which keys each transaction type
        promises to carry, and checking presence here means a
        caller-bug (missing ``sender_uid``, wrong key name) fails at
        construction rather than producing a corrupted
        ``TransactionDocument`` inside a Firestore commit.
        """
        required = _REQUIRED_METADATA_KEYS.get(self.transaction_type)
        if required is None:
            # Should be unreachable — TransactionType is a closed enum
            # and _REQUIRED_METADATA_KEYS covers every member.
            raise ValueError(
                f"No metadata contract defined for transaction type "
                f"{self.transaction_type.value!r}."
            )

        missing = required - self.metadata.keys()
        if missing:
            raise ValueError(
                f"metadata is missing required keys for "
                f"{self.transaction_type.value}: "
                f"{', '.join(sorted(missing))}."
            )

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


# The keys a counterparty snapshot dict must carry. A snapshot freezes
# the counterparty's tag and display name as they were at the moment
# the transaction settled, so a later rename or retag never rewrites
# how a past transaction is displayed. ``avatar_url`` is deliberately
# excluded: a photo isn't a financial fact the way a name is, it's
# decoration that should always reflect who the user is *today* — a
# frontend that wants an avatar next to a transaction fetches the
# current profile for that specific counterparty. ``uid`` is also
# excluded: it's already available as ``sender_uid`` / ``recipient_uid``
# on the transaction document, so repeating it here would just be a
# second source of truth for the same value.
_SNAPSHOT_KEYS: frozenset[str] = frozenset({"tag", "name"})


def _validate_snapshot(
    snapshot: dict[str, str] | None, label: str
) -> None:
    """Validate one counterparty snapshot dict, if present.

    A snapshot is optional enrichment — see
    ``TransactionDocument._verify_snapshots`` for when one is allowed
    to be absent. This helper only checks the shape of a snapshot
    that is actually present.

    Args:
        snapshot: The snapshot dict, or None.
        label: Which field this is, for error messages
            ("sender_snapshot" or "recipient_snapshot").

    Raises:
        TypeError: snapshot is not a dict.
        ValueError: snapshot's keys don't exactly match
            ``_SNAPSHOT_KEYS``, or tag/name is missing or empty.
    """
    if snapshot is None:
        return

    if not isinstance(snapshot, dict):
        raise TypeError(
            f"{label} must be a dict or None, got "
            f"{type(snapshot).__name__}."
        )

    missing = _SNAPSHOT_KEYS - snapshot.keys()
    extra = snapshot.keys() - _SNAPSHOT_KEYS
    if missing or extra:
        raise ValueError(
            f"{label} must have exactly the keys {sorted(_SNAPSHOT_KEYS)}; "
            f"missing={sorted(missing)}, unexpected={sorted(extra)}."
        )

    for key in ("tag", "name"):
        value = snapshot[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label}[{key!r}] must be a non-empty string.")


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

    A separate ``failed_transfer_attempts`` collection, written by the
    transfers service on rejection, is the intended path for that
    audit trail if it is ever needed.

    ``sender_snapshot`` and ``recipient_snapshot`` each hold
    ``{"tag", "name"}`` for that side, frozen at the moment of
    settlement — see the module docstring. Either may be None: a
    snapshot is optional enrichment, not a requirement of a valid
    transaction. The one constraint enforced here is that a snapshot
    can never exist without its uid — see ``_verify_snapshots``.

    ``from_currency``/``from_amount_minor`` and ``to_currency``/
    ``to_amount_minor`` are each nullable as a pair: FUNDING has no
    "from" side, WITHDRAWAL has no "to" side, and both are present
    for TRANSFER and REVERSAL. See ``_verify_amounts_and_currencies``.
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

        self._verify_amounts_and_currencies()
        self._verify_snapshots()

    def _verify_amounts_and_currencies(self) -> None:
        """Validate the from/to currency-and-amount pair on each side.

        FUNDING has no "from" side and WITHDRAWAL has no "to" side —
        that side's external leg is outside the ledger, so its
        currency and amount are both None. Unlike a snapshot, an
        amount is never valid without its currency: this pairing is
        the financial fact the document records, not an enrichment,
        so both directions of it are enforced.
        """
        if (self.from_amount_minor is None) != (self.from_currency is None):
            raise ValueError(
                "from_amount_minor and from_currency must be both "
                "present or both None."
            )
        if (self.to_amount_minor is None) != (self.to_currency is None):
            raise ValueError(
                "to_amount_minor and to_currency must be both present "
                "or both None."
            )

        if self.from_amount_minor is not None and self.from_amount_minor <= 0:
            raise ValueError(
                "from_amount_minor must be greater than zero when present."
            )
        if self.to_amount_minor is not None and self.to_amount_minor <= 0:
            raise ValueError(
                "to_amount_minor must be greater than zero when present."
            )
        if self.fee_minor < 0:
            raise ValueError("fee_minor cannot be negative.")

        cross_currency = (
            self.from_currency is not None
            and self.to_currency is not None
            and self.from_currency != self.to_currency
        )
        if cross_currency and self.rate_scaled is None:
            raise ValueError(
                "rate_scaled is required for a cross-currency transaction."
            )
        if not cross_currency and self.rate_scaled is not None:
            raise ValueError(
                "rate_scaled must be None unless from_currency and "
                "to_currency are both present and differ."
            )

    def _verify_snapshots(self) -> None:
        """Each snapshot must be well-formed, and can't exist without its uid.

        Snapshots are optional enrichment: a uid with no snapshot is a
        valid, if less informative, transaction record — the frontend
        falls back to showing the uid or fetching the profile on
        demand. The reverse is never valid: a snapshot with no owning
        uid can't correspond to any account and is always a caller
        bug, so that one direction is still enforced.
        """
        _validate_snapshot(self.sender_snapshot, "sender_snapshot")
        _validate_snapshot(self.recipient_snapshot, "recipient_snapshot")

        if self.sender_snapshot is not None and self.sender_uid is None:
            raise ValueError(
                "sender_snapshot is present but sender_uid is None."
            )
        if self.recipient_snapshot is not None and self.recipient_uid is None:
            raise ValueError(
                "recipient_snapshot is present but recipient_uid is None."
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