"""End-to-end transfer tests against a live local server.

Requires the two demo users to have been seeded first:

    python -m scripts.seed_demo_users

Then run the tests with the FastAPI app up:

    pytest tests/test_transfers.py -v -s
"""

import os
import time
from collections.abc import Iterator
from decimal import ROUND_FLOOR, Decimal

import httpx
import pytest
from dotenv import load_dotenv

from app.core.constants import CURRENCY_MINOR_UNITS, Currency
from app.features.accounts import service as accounts_service

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)

TEST_PASSWORD = "test1234"
TEST_PIN = "48392"
WRONG_PIN = "11111"

SENDER_EMAIL = os.environ.get(
    "TEST_SENDER_EMAIL", "codewithkakes@gmail.com"
)
RECIPIENT_EMAIL = os.environ.get(
    "TEST_RECIPIENT_EMAIL", "code2withkakes@gmail.com"
)

SEND_AMOUNT_MINOR = 50000  # GHS 500.00


def _sign_in(email: str, web_api_key: str) -> dict:
    """Sign in an existing Firebase user and return {uid, id_token}."""
    r = httpx.post(
        FIREBASE_SIGNIN_URL,
        params={"key": web_api_key},
        json={"email": email, "password": TEST_PASSWORD, "returnSecureToken": True},
        timeout=15.0,
    )
    r.raise_for_status()
    payload = r.json()
    return {"uid": payload["localId"], "id_token": payload["idToken"]}


def _unique_key(prefix: str = "test") -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def _expected_receive_minor(
    *,
    send_amount_minor: int,
    sender_currency: str,
    recipient_currency: str,
    rate: str,
) -> int:
    """Independently recompute the expected receive amount.

    Deliberately written from scratch here rather than calling
    ``fee_calculator.compute`` — asserting the API's output against a
    call to the very function under test would just prove the function
    agrees with itself, not that either is correct. This does the
    dimensional analysis fresh: minor units of the sender's currency,
    divided by the sender's minor-unit multiplier to get major units,
    times the rate, times the recipient's minor-unit multiplier, floored.

    This is the check that would have caught the missing-division-by-
    from_units bug: that bug produced a value exactly 100x this one for
    any currency pair where the sender's currency has 100 minor units
    (i.e. every pair except an XOF sender), because it applied the rate
    directly to the minor-unit amount instead of the major-unit amount.
    A bare "> 0" or a self-referential balance-delta check would not
    have caught that; this does, because it's computed independently of
    whatever the service actually returned.
    """
    from_units = CURRENCY_MINOR_UNITS[Currency(sender_currency)]
    to_units = CURRENCY_MINOR_UNITS[Currency(recipient_currency)]
    send_major = Decimal(send_amount_minor) / Decimal(from_units)
    receive_major = send_major * Decimal(rate)
    receive_minor = receive_major * Decimal(to_units)
    return int(receive_minor.to_integral_value(rounding=ROUND_FLOOR))


@pytest.fixture(scope="session")
def web_api_key() -> str:
    key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not key:
        pytest.skip("FIREBASE_WEB_API_KEY is not set in .env")
    return key


@pytest.fixture(scope="session")
def sender(web_api_key: str) -> dict:
    return _sign_in(SENDER_EMAIL, web_api_key)


@pytest.fixture(scope="session")
def recipient(web_api_key: str) -> dict:
    return _sign_in(RECIPIENT_EMAIL, web_api_key)


@pytest.fixture(scope="session")
def sender_tag(sender: dict) -> str:
    from app.features.users import service as users_service

    return users_service.get_profile(sender["uid"])["tag"]


@pytest.fixture(scope="session")
def recipient_tag(recipient: dict) -> str:
    from app.features.users import service as users_service

    return users_service.get_profile(recipient["uid"])["tag"]


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=30.0) as c:
        yield c


@pytest.fixture
def sender_headers(sender: dict) -> dict:
    return {"Authorization": f"Bearer {sender['id_token']}"}


def test_health() -> None:
    r = httpx.get(f"{BASE_URL}/health", timeout=10.0)
    assert r.status_code == 200, r.text


def test_quote_happy_path(
    client: httpx.Client, sender_headers: dict, recipient_tag: str
) -> None:
    r = client.post(
        "/transfers/quote",
        headers=sender_headers,
        json={"recipient_tag": recipient_tag, "amount_minor": SEND_AMOUNT_MINOR},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["sender_currency"] == Currency.GHS.value
    assert data["recipient"]["tag"] == recipient_tag
    assert data["send_amount_minor"] == SEND_AMOUNT_MINOR
    assert data["fee_minor"] == 500
    assert data["total_debit_minor"] == SEND_AMOUNT_MINOR + 500

    # Not "> 0" — that passes for a value of any magnitude, including
    # one that's off by 100x. Recompute independently from the rate the
    # API itself returned and require an exact match.
    expected_receive = _expected_receive_minor(
        send_amount_minor=data["send_amount_minor"],
        sender_currency=data["sender_currency"],
        recipient_currency=data["recipient"]["currency"],
        rate=data["rate"],
    )
    assert data["receive_amount_minor"] == expected_receive


def test_quote_rejects_unknown_recipient(
    client: httpx.Client, sender_headers: dict
) -> None:
    r = client.post(
        "/transfers/quote",
        headers=sender_headers,
        json={"recipient_tag": "nobodyxyz.ng", "amount_minor": SEND_AMOUNT_MINOR},
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "RECIPIENT_NOT_FOUND"


def test_quote_rejects_self_transfer(
    client: httpx.Client, sender_headers: dict, sender_tag: str
) -> None:
    r = client.post(
        "/transfers/quote",
        headers=sender_headers,
        json={"recipient_tag": sender_tag, "amount_minor": SEND_AMOUNT_MINOR},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "SELF_TRANSFER"


def test_execute_settles_and_moves_money(
    client: httpx.Client,
    sender: dict,
    sender_headers: dict,
    recipient: dict,
    recipient_tag: str,
) -> None:
    sender_before = accounts_service.get_balance_minor(sender["uid"])
    recipient_before = accounts_service.get_balance_minor(recipient["uid"])

    r = client.post(
        "/transfers",
        headers=sender_headers,
        json={
            "recipient_tag": recipient_tag,
            "amount_minor": SEND_AMOUNT_MINOR,
            "idempotency_key": _unique_key("exec-ok"),
            "pin": TEST_PIN,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == "SETTLED"
    assert data["transaction_id"]
    quote = data["quote"]

    # Same reasoning as test_quote_happy_path: verify the amount the
    # API says it applied is itself correct, not just that the ledger
    # faithfully moved whatever number the service happened to compute.
    expected_receive = _expected_receive_minor(
        send_amount_minor=quote["send_amount_minor"],
        sender_currency=quote["sender_currency"],
        recipient_currency=quote["recipient"]["currency"],
        rate=quote["rate"],
    )
    assert quote["receive_amount_minor"] == expected_receive

    sender_after = accounts_service.get_balance_minor(sender["uid"])
    recipient_after = accounts_service.get_balance_minor(recipient["uid"])

    # These two checks verify a different thing: that the ledger
    # actually applied the amounts the service computed. They're
    # necessary but not sufficient on their own — see the expected_receive
    # assertion above for why.
    assert sender_before - sender_after == quote["total_debit_minor"]
    assert recipient_after - recipient_before == quote["receive_amount_minor"]


def test_execute_rejects_wrong_pin(
    client: httpx.Client,
    sender: dict,
    sender_headers: dict,
    recipient_tag: str,
) -> None:
    before = accounts_service.get_balance_minor(sender["uid"])
    r = client.post(
        "/transfers",
        headers=sender_headers,
        json={
            "recipient_tag": recipient_tag,
            "amount_minor": SEND_AMOUNT_MINOR,
            "idempotency_key": _unique_key("exec-badpin"),
            "pin": WRONG_PIN,
        },
    )
    # Checked as a correlated pair, not two independent `in` checks —
    # two independent checks would also pass for a mismatched
    # combination like 429 paired with PIN_INVALID, which should never
    # happen given how PinInvalidError (422) and PinLockedError (429)
    # are defined.
    code = r.json()["error"]["code"]
    if r.status_code == 422:
        assert code == "PIN_INVALID", r.text
    elif r.status_code == 429:
        assert code == "PIN_LOCKED", r.text
    else:
        pytest.fail(f"Unexpected status code {r.status_code}: {r.text}")

    after = accounts_service.get_balance_minor(sender["uid"])
    assert before == after


def test_execute_is_idempotent(
    client: httpx.Client,
    sender: dict,
    sender_headers: dict,
    recipient_tag: str,
) -> None:
    key = _unique_key("exec-idem")
    before = accounts_service.get_balance_minor(sender["uid"])

    first = client.post(
        "/transfers",
        headers=sender_headers,
        json={
            "recipient_tag": recipient_tag,
            "amount_minor": SEND_AMOUNT_MINOR,
            "idempotency_key": key,
            "pin": TEST_PIN,
        },
    )
    assert first.status_code == 201, first.text
    debit = first.json()["data"]["quote"]["total_debit_minor"]

    second = client.post(
        "/transfers",
        headers=sender_headers,
        json={
            "recipient_tag": recipient_tag,
            "amount_minor": SEND_AMOUNT_MINOR,
            "idempotency_key": key,
            "pin": TEST_PIN,
        },
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "DUPLICATE_TRANSFER"

    after = accounts_service.get_balance_minor(sender["uid"])
    assert before - after == debit