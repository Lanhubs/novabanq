"""Funding service.

Orchestrates the funding flow: creating a virtual account for a user,
and crediting their balance when a deposit arrives.

Two entry points:

    * ``create_virtual_account(uid)`` — get-or-create the user's
      virtual account and return it. Idempotent; the second call for
      the same uid returns the same account unchanged.
    * ``handle_webhook(payload)`` — process a provider webhook that a
      deposit has arrived. Credits the ledger atomically and
      idempotently.

Both delegate the actual money movement to the ledger. This service
never writes ``balance_minor``.

Webhook failure policy:
    The webhook returns a 200 for every event that reaches
    ``handle_webhook``, whether it credited, was a duplicate, or was
    rejected as corrupt. Non-transient failures — unknown reference,
    stale reference, currency mismatch — are logged at ``critical``
    so monitoring can alert on them, but they do not raise, because
    raising would make Flutterwave retry a webhook that will never
    succeed. The only exceptions that propagate out of this module
    are infrastructure failures (``FundingRepositoryError``,
    ``LedgerRepositoryError``), which ARE transient — a Firestore
    outage should be retried, so a non-200 is correct in that case.

Signature verification is NOT done here. The router is responsible
for verifying the provider's signature header before the payload
reaches this service. See ``app.features.funding.router``.
"""

import logging
from decimal import ROUND_HALF_EVEN

from app.core.constants import (
    CURRENCY_MINOR_UNITS,
    AccountType,
    Country,
    Currency,
    EntryDirection,
    SystemAccountPurpose,
    TransactionType,
    system_account_id,
)
from app.features.accounts import repository as accounts_repository
from app.features.funding import repository
from app.features.funding.schemas import (
    VirtualAccountResponse,
    WebhookAck,
    WebhookPayload,
)
from app.features.ledger import service as ledger_service
from app.features.ledger.schemas import (
    LedgerInstruction,
    LedgerRequest,
)
from app.features.users import service as users_service
from app.infra.virtual_accounts import get_virtual_account_provider
from app.infra.virtual_accounts.base import VirtualAccount

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_virtual_account(uid: str) -> VirtualAccountResponse:
    """Return the user's virtual account, creating it if absent.

    Idempotent. The first call generates a provider reference,
    creates the funding record, and writes the reverse-lookup
    document — all inside one Firestore transaction. Subsequent calls
    return the same account unchanged.

    Args:
        uid: Firebase uid of the caller.

    Returns:
        A populated ``VirtualAccountResponse``.

    Raises:
        UserNotFoundError: If the caller has no profile.
        FundingRepositoryError: On a Firestore failure.
    """
    existing = repository.get_funding_record(uid)
    if existing is not None:
        return _response_from_record(existing)

    profile = users_service.get_profile(uid)

    # Firestore stores country and currency as raw strings — the enum
    # members are not preserved across the wire. Coerce both here so
    # the provider receives the enum members its interface declares,
    # matching how transfers/service.py and users/service.py handle
    # the same fields.
    provider = get_virtual_account_provider()
    account: VirtualAccount = provider.create_virtual_account(
        uid=uid,
        account_name=_display_name(profile),
        country=Country(profile["country"]),
        currency=Currency(profile["currency"]),
        email=profile.get("email") or "",
        phone=profile.get("phone") or "",
    )

    record, created = repository.get_or_create(
        uid,
        account_number=account.account_number,
        bank_name=account.bank_name,
        account_name=account.account_name,
        currency=account.currency,
        country=account.country,
        provider_ref=account.provider_ref,
    )

    if not created:
        logger.info(
            "Virtual account already existed for uid=%s; returning "
            "stored record. The provider_ref generated this turn "
            "(%s) was discarded.",
            uid,
            account.provider_ref,
        )

    return _response_from_record(record)


def handle_webhook(payload: WebhookPayload) -> WebhookAck:
    """Process a deposit webhook from the provider.

    Credits the user's balance through the ledger when the webhook
    reports a successful deposit, and returns a 200-shaped ack in
    every case. See the module docstring for why non-transient
    failures do not raise.

    Args:
        payload: The parsed webhook payload. The router has already
            verified the request signature before calling this.

    Returns:
        A ``WebhookAck`` describing whether the ledger was credited.

    Raises:
        FundingRepositoryError: On a Firestore read failure while
            resolving the reference or the funding record.
        LedgerRepositoryError: On a Firestore failure while committing
            the credit.
    """
    if payload.event != "charge.completed":
        logger.info("Ignoring webhook event=%s.", payload.event)
        return WebhookAck(status="ok", credited=False)

    if payload.data.status != "successful":
        logger.info(
            "Ignoring webhook with status=%s for tx_ref=%s.",
            payload.data.status,
            payload.data.tx_ref,
        )
        return WebhookAck(status="ok", credited=False)

    provider_ref = payload.data.tx_ref

    uid = repository.get_uid_for_ref(provider_ref)
    if uid is None:
        logger.critical(
            "Webhook references unknown provider_ref=%s event_id=%s. "
            "Refusing to credit.",
            provider_ref,
            payload.data.id,
        )
        return WebhookAck(status="ok", credited=False)

    record = repository.get_funding_record(uid)
    if record is None:
        logger.critical(
            "Provider ref %s resolves to uid=%s but no funding record "
            "exists. The two documents should be written in one "
            "transaction; this indicates corruption or a manually "
            "deleted record.",
            provider_ref,
            uid,
        )
        return WebhookAck(status="ok", credited=False)

    if record.get("provider_ref") != provider_ref:
        logger.critical(
            "Webhook provider_ref=%s does not match the current ref "
            "on file for uid=%s (which is %s). Refusing to credit — "
            "this webhook references a stale virtual account.",
            provider_ref,
            uid,
            record.get("provider_ref"),
        )
        return WebhookAck(status="ok", credited=False)

    record_currency = Currency(record["currency"])
    if record_currency != payload.data.currency:
        logger.critical(
            "Webhook currency=%s does not match funding record "
            "currency=%s for uid=%s provider_ref=%s.",
            payload.data.currency.value,
            record_currency.value,
            uid,
            provider_ref,
        )
        return WebhookAck(status="ok", credited=False)

    amount_minor = int(
        (payload.data.amount * CURRENCY_MINOR_UNITS[record_currency])
        .to_integral_value(rounding=ROUND_HALF_EVEN)
    )
    if amount_minor <= 0:
        logger.critical(
            "Webhook for uid=%s provider_ref=%s resolves to "
            "non-positive amount_minor=%d. Refusing to credit.",
            uid,
            provider_ref,
            amount_minor,
        )
        return WebhookAck(status="ok", credited=False)

    # The ledger requires the USER account document to exist before
    # it can credit it. get_or_create is a no-op if the account is
    # already there.
    accounts_repository.get_or_create(uid, record_currency.value)

    result = _credit_via_ledger(
        uid=uid,
        currency=record_currency,
        amount_minor=amount_minor,
        webhook_event_id=payload.data.id,
    )

    if result.duplicate:
        logger.info(
            "Webhook event_id=%s is a replay; original credit already "
            "applied for uid=%s.",
            payload.data.id,
            uid,
        )
        return WebhookAck(status="ok", credited=False)

    logger.info(
        "Credited %d %s to uid=%s from provider_ref=%s event_id=%s.",
        amount_minor,
        record_currency.value,
        uid,
        provider_ref,
        payload.data.id,
    )
    return WebhookAck(status="ok", credited=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _credit_via_ledger(
    *,
    uid: str,
    currency: Currency,
    amount_minor: int,
    webhook_event_id: str,
):
    """Credit the user's account through the ledger.

    Builds a two-leg FUNDING request — debit the FX bridge, credit
    the user — with an idempotency key derived from the provider's
    webhook event id. A replayed webhook produces the same key, which
    the ledger recognizes and returns as ``duplicate=True`` without
    moving money again.

    Returns the ``LedgerResult`` so the caller can distinguish a fresh
    credit from a replay.
    """
    funding_account = system_account_id(
        SystemAccountPurpose.FX_BRIDGE, currency
    )

    debit_funding = LedgerInstruction(
        account_id=funding_account,
        account_type=AccountType.SYSTEM,
        currency=currency,
        direction=EntryDirection.DEBIT,
        amount_minor=amount_minor,
    )
    credit_user = LedgerInstruction(
        account_id=uid,
        account_type=AccountType.USER,
        currency=currency,
        direction=EntryDirection.CREDIT,
        amount_minor=amount_minor,
    )

    request = LedgerRequest(
        transaction_id=_new_transaction_id(webhook_event_id),
        idempotency_key=f"funding-{webhook_event_id}",
        transaction_type=TransactionType.FUNDING,
        instructions=(debit_funding, credit_user),
        metadata={
            "recipient_uid": uid,
            "to_currency": currency.value,
            "to_amount_minor": amount_minor,
            "fee_minor": 0,
        },
    )

    return ledger_service.debit_and_credit(request)


def _new_transaction_id(webhook_event_id: str) -> str:
    """Derive a deterministic transaction id from the webhook event.

    Deterministic rather than random so that two concurrent deliveries
    of the same webhook (which can happen before the idempotency
    check inside the ledger commits) attempt to write the same
    ``transactions/{id}`` document. The second write loses the race —
    Firestore's transaction isolation rejects it, and the retry finds
    the committed idempotency record. A random transaction id would
    let the second delivery write a second ``transactions`` document,
    producing two records of one deposit.

    The returned id is a UUIDv5 (deterministic) computed from the
    webhook event id. It is stable across calls and unique per event.
    """
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"novabanq-funding-{webhook_event_id}"))


def _response_from_record(record: dict) -> VirtualAccountResponse:
    """Project a stored funding record into the response model."""
    return VirtualAccountResponse(
        account_number=record["account_number"],
        bank_name=record["bank_name"],
        account_name=record["account_name"],
        currency=Currency(record["currency"]),
        country=Country(record["country"]),
        provider_ref=record["provider_ref"],
        created_at=record["created_at"],
    )


def _display_name(profile: dict) -> str:
    """Join the profile's name fields into a single display name.

    Mirrors ``transfers.service._display_name`` and
    ``notifications.service._display_name_of`` so a given user's
    display name is identical everywhere it appears.
    """
    parts = [
        profile.get("first_name", ""),
        profile.get("middle_name", ""),
        profile.get("last_name", ""),
    ]
    return " ".join(p for p in parts if p).strip() or "NovaBanq User"