"""Seed two demo users for local development and the transfer test.

Creates (idempotently) two Firebase users and their NovaBanq profiles:

    * Kwame Mensah   — Ghanaian, GHS account, funded.
    * Temi Adeyemi   — Nigerian, NGN account, funded.

All balance movements go through the ledger. The seed script debits
the FX bridge system account and credits the user's account, so the
ledger's per-currency balance invariant holds and the resulting
balances are indistinguishable from production-funded ones. The FX
bridge will carry a negative balance afterwards, which is correct —
system accounts track what the platform owes or holds pending
settlement, and the ledger explicitly permits system accounts to go
negative.

The seed also force-refreshes the live GHS → NGN FX rate from the
provider before doing anything else. This proves the FX provider is
reachable right now, and writes a fresh rate to ``corridors/GHS_NGN``
so the first quote the frontend requests is priced off a rate fetched
seconds ago, not a value that has been sitting in Firestore since the
last time someone ran the corridor seed script.

Run once from the repo root:

    python -m scripts.seed_demo_users

Safe to re-run: every step checks for existing state first, the
funding step tops the user up to a target balance rather than adding
to it, and the rate refresh is a read-through-write with no side
effects on the ledger.
"""

import os
import uuid

import httpx
from dotenv import load_dotenv
from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.constants import (
    AccountType,
    Country,
    Currency,
    EntryDirection,
    FirestoreCollection,
    SystemAccountPurpose,
    TransactionType,
    system_account_id,
)
from app.features.accounts import repository as accounts_repository
from app.features.accounts import service as accounts_service
from app.features.currency import service as currency_service
from app.features.ledger import service as ledger_service
from app.features.ledger.schemas import (
    LedgerInstruction,
    LedgerRequest,
)
from app.features.users import repository as users_repository
from app.features.users import service as users_service
from app.infra.firestore import document

load_dotenv()

FIREBASE_SIGNUP_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)

DEMO_PASSWORD = "test1234"
DEMO_PIN = "48392"

# Target balance for each demo user, in minor units of their own currency.
DEMO_TARGET_BALANCE_MINOR = 5_000_000


DEMO_USERS = [
    {
        "email": os.environ.get("DEMO_SENDER_EMAIL", "codewithkakes@gmail.com"),
        "first_name": "David",
        "middle_name": "Chashama",
        "last_name": "Mensah",
        "country": Country.GHANA,
        "phone": "+233201234567",
        "base_tag": "davidkampe",
    },
    {
        "email": os.environ.get(
            "DEMO_RECIPIENT_EMAIL", "code2withkakes@gmail.com"
        ),
        "first_name": "Okoro",
        "middle_name": "Chidera",
        "last_name": "Nzubem",
        "country": Country.NIGERIA,
        "phone": "+2348012345678",
        "base_tag": "chidera",
    },
]


# ---------------------------------------------------------------------------
# Firebase
# ---------------------------------------------------------------------------

def _firebase_user(email: str, web_api_key: str) -> dict:
    """Sign up or sign in a Firebase user. Returns {uid, id_token}."""
    signup = httpx.post(
        FIREBASE_SIGNUP_URL,
        params={"key": web_api_key},
        json={"email": email, "password": DEMO_PASSWORD, "returnSecureToken": True},
        timeout=15.0,
    )
    if signup.status_code == 200:
        payload = signup.json()
    else:
        message = signup.json().get("error", {}).get("message", "")
        if message != "EMAIL_EXISTS":
            signup.raise_for_status()
        signin = httpx.post(
            FIREBASE_SIGNIN_URL,
            params={"key": web_api_key},
            json={"email": email, "password": DEMO_PASSWORD, "returnSecureToken": True},
            timeout=15.0,
        )
        signin.raise_for_status()
        payload = signin.json()
    return {"uid": payload["localId"], "id_token": payload["idToken"]}


# ---------------------------------------------------------------------------
# Live FX rate
# ---------------------------------------------------------------------------

def _refresh_live_rate(from_currency: Currency, to_currency: Currency) -> None:
    """Force-refresh a corridor from the live FX provider and log it.

    Calls the currency service's ``refresh_corridor``, which bypasses
    the cache freshness check and always hits FxRatesAPI. On success,
    the corridor document in Firestore is updated with the new rate and
    a fresh ``fetched_at``. On failure — provider down, auth rejected,
    network unreachable — the underlying exception propagates and the
    seed aborts, because a demo that cannot price a transfer is not
    worth seeding.

    Args:
        from_currency: The corridor's source currency.
        to_currency: The corridor's target currency.

    Raises:
        RateUnavailableError: If the live provider cannot be reached
            and no cache is usable.
        FxRatesClientError: If the provider responds with an error or
            an unparseable payload.
    """
    pair = f"{from_currency.value} → {to_currency.value}"
    print(f"Refreshing live FX rate for {pair} ...")

    rate = currency_service.refresh_corridor(from_currency, to_currency)

    print(
        f"  rate:       {rate.rate}\n"
        f"  source:     {rate.source.value}\n"
        f"  fetched_at: {rate.fetched_at.isoformat()}"
    )
    print()


# ---------------------------------------------------------------------------
# System accounts
# ---------------------------------------------------------------------------

def _ensure_system_account(purpose: SystemAccountPurpose, currency: Currency) -> None:
    """Create a system account document with a zero balance if absent.

    The ledger requires every system account it touches to exist as a
    document. This creates the document with ``balance_minor = 0`` on
    first run and leaves it untouched on every subsequent run — the
    ledger is the only writer of ``balance_minor`` after creation.

    Idempotent.
    """
    account_id = system_account_id(purpose, currency)
    ref = document(FirestoreCollection.SYSTEM_ACCOUNTS, account_id)
    snapshot = ref.get()

    if snapshot.exists:
        return

    ref.set(
        {
            "account_id": account_id,
            "purpose": purpose.value,
            "currency": currency.value,
            "account_type": AccountType.SYSTEM.value,
            "balance_minor": 0,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
    )
    print(f"  created system account {account_id} (balance 0)")


# ---------------------------------------------------------------------------
# Funding via the ledger
# ---------------------------------------------------------------------------

def _current_balance(uid: str) -> int:
    """Return the user's current balance_minor, or 0 if no account."""
    return accounts_service.get_balance_minor(uid)


def _fund_to_target(uid: str, currency: Currency, target_minor: int) -> None:
    """Top the user's account up to ``target_minor`` via the ledger.

    Computes the delta between the current balance and the target. If
    the user already holds at least the target, does nothing. Otherwise
    debits the FX bridge system account and credits the user's account
    for the difference, through the ledger, so per-currency debits
    equal credits and the user's balance is genuinely ledger-backed.

    The FX bridge will go negative as a result. That is expected —
    system accounts track what the platform holds pending settlement
    and are permitted to carry a negative balance.

    Idempotent: running twice with the same target does nothing the
    second time (the balance is already at target).
    """
    current = _current_balance(uid)
    if current >= target_minor:
        print(f"  balance already at or above target ({current}), skipping")
        return

    delta = target_minor - current
    funding_account = system_account_id(SystemAccountPurpose.FX_BRIDGE, currency)

    debit_funding = LedgerInstruction(
        account_id=funding_account,
        account_type=AccountType.SYSTEM,
        currency=currency,
        direction=EntryDirection.DEBIT,
        amount_minor=delta,
    )
    credit_user = LedgerInstruction(
        account_id=uid,
        account_type=AccountType.USER,
        currency=currency,
        direction=EntryDirection.CREDIT,
        amount_minor=delta,
    )

    request = LedgerRequest(
        transaction_id=str(uuid.uuid4()),
        idempotency_key=f"seed-fund-{uid}-{delta}",
        transaction_type=TransactionType.FUNDING,
        instructions=(debit_funding, credit_user),
        metadata={
            "recipient_uid": uid,
            "to_currency": currency.value,
            "to_amount_minor": delta,
            "fee_minor": 0,
        },
    )

    ledger_service.debit_and_credit(request)
    print(f"  credited {delta} via ledger from {funding_account}")


# ---------------------------------------------------------------------------
# User seeding
# ---------------------------------------------------------------------------

def _ensure_pin(uid: str, pin: str) -> None:
    """Force the user's PIN to ``pin``, idempotently."""
    profile = users_service.get_profile(uid)
    if profile.get("pin_hash"):
        users_repository.clear_pin(uid)
    users_service.set_pin(uid, pin)


def _seed_user(spec: dict, web_api_key: str) -> dict:
    """Create Firebase user + profile + tag + PIN + funded balance."""
    identity = _firebase_user(spec["email"], web_api_key)
    uid = identity["uid"]

    try:
        profile = users_service.get_profile(uid)
        print(f"  profile exists: @{profile.get('tag') or '(no tag)'}")
    except Exception:
        print("  creating profile ...")
        profile = users_service.create_profile(
            uid,
            first_name=spec["first_name"],
            middle_name=spec["middle_name"],
            last_name=spec["last_name"],
            country=spec["country"],
            phone=spec["phone"],
            email=spec["email"],
            claims={"firebase": {"sign_in_provider": "google.com"}},
        )

    if not profile.get("tag"):
        print(f"  claiming tag '{spec['base_tag']}' ...")
        users_service.claim_tag(uid, spec["base_tag"])
        profile = users_service.get_profile(uid)

    print("  ensuring account row ...")
    accounts_repository.get_or_create(uid, profile["currency"])

    print("  setting PIN ...")
    _ensure_pin(uid, DEMO_PIN)

    currency = Currency(profile["currency"])
    print(f"  funding via ledger to {DEMO_TARGET_BALANCE_MINOR} {currency.value} ...")
    _fund_to_target(uid, currency, DEMO_TARGET_BALANCE_MINOR)

    return {
        "uid": uid,
        "email": spec["email"],
        "tag": profile["tag"],
        "currency": profile["currency"],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    # Force a live fetch of the GHS → NGN corridor before anything else.
    # This proves the FX provider is reachable right now and writes a
    # fresh rate to Firestore, so the first quote the frontend requests
    # is priced off a rate fetched seconds ago. A demo that cannot price
    # a transfer is not worth seeding — fail here rather than later with
    # an unrelated-looking error.
    _refresh_live_rate(Currency.GHS, Currency.NGN)

    # The transfer corridor is GHS ↔ NGN. The transfer needs fx_GHS,
    # fee_GHS, fx_NGN, fee_NGN. Funding needs fx_GHS and fx_NGN (both
    # already in the list). Four system accounts total.
    print("Ensuring system accounts exist:")
    for currency in (Currency.GHS, Currency.NGN):
        for purpose in (
            SystemAccountPurpose.FX_BRIDGE,
            SystemAccountPurpose.FEE_COLLECTOR,
        ):
            _ensure_system_account(purpose, currency)

    print()
    print("Seeding demo users:")
    results = []
    for spec in DEMO_USERS:
        print(f"- {spec['email']}")
        results.append(_seed_user(spec, web_api_key))

    print()
    print("=" * 60)
    print("Seeded users:")
    for r in results:
        print(f"  uid:      {r['uid']}")
        print(f"  email:    {r['email']}")
        print(f"  tag:      @{r['tag']}")
        print(f"  currency: {r['currency']}")
        print(f"  PIN:      {DEMO_PIN}")
        print(f"  password: {DEMO_PASSWORD}")
        print()
    print("Set these in .env for tests/test_transfers.py:")
    print(f"  TEST_SENDER_EMAIL={results[0]['email']}")
    print(f"  TEST_RECIPIENT_EMAIL={results[1]['email']}")
    print("=" * 60)


if __name__ == "__main__":
    main()