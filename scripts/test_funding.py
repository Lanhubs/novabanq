"""Live smoke test for the funding endpoints.

Creates a virtual account for each demo user, then fires a mock
webhook for each and confirms the ledger credited the balance.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * The demo users seeded (python -m scripts.seed_demo_users)

Run:
    python -m scripts.test_funding
"""

import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
PASSWORD = "test1234"

SENDER_EMAIL = os.environ.get("TEST_SENDER_EMAIL", "codewithkakes@gmail.com")
RECIPIENT_EMAIL = os.environ.get("TEST_RECIPIENT_EMAIL", "code2withkakes@gmail.com")


def _sign_in(email: str, web_api_key: str) -> dict:
    r = httpx.post(
        FIREBASE_SIGNIN_URL,
        params={"key": web_api_key},
        json={"email": email, "password": PASSWORD, "returnSecureToken": True},
        timeout=15.0,
    )
    r.raise_for_status()
    p = r.json()
    return {"uid": p["localId"], "id_token": p["idToken"]}


def _print(label: str, response: httpx.Response) -> dict:
    print(f"\n=== {label} ===")
    print(f"status: {response.status_code}")
    body = response.json()
    print(body)
    return body


def _unique_event_id(prefix: str = "test-event") -> str:
    """Return a fresh event id for this run.

    The ledger's idempotency check treats the event id as the key, so
    a fixed id means only the first run of this script ever credits —
    every subsequent run is a correctly-detected duplicate. Using a
    timestamp-based suffix gives the fresh-deposit step a genuinely
    new event each run, while the replay step reuses the exact same
    id so the duplicate path is still exercised.
    """
    return f"{prefix}-{int(time.time() * 1000)}"


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    sender = _sign_in(SENDER_EMAIL, web_api_key)

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {sender['id_token']}"}

        # 1. Create the virtual account
        r = c.post("/funding/virtual-account", headers=headers)
        body = _print("Create virtual account", r)
        va = body["data"]
        provider_ref = va["provider_ref"]

        # 2. Fire a webhook for that account, simulating a deposit.
        #    The event id is fresh this run so the ledger treats it as
        #    a new deposit, not a replay of an earlier test.
        webhook_payload = {
            "event": "charge.completed",
            "data": {
                "id": _unique_event_id(),
                "tx_ref": provider_ref,
                "amount": 250.00,
                "currency": va["currency"],
                "status": "successful",
            },
        }
        r = c.post("/webhooks/flutterwave", json=webhook_payload)
        _print("Webhook (fresh deposit)", r)

        # 3. Fire the same webhook again — same event id, so the
        #    ledger's idempotency check rejects it and no second
        #    credit moves. Expect credited=False.
        r = c.post("/webhooks/flutterwave", json=webhook_payload)
        _print("Webhook (replay, expect credited=False)", r)

        # 4. Check the balance. It should be higher by exactly
        #    250.00 in major units (25000 minor) than before the run.
        r = c.get("/accounts/me", headers=headers)
        _print("Balance after funding", r)

        # 5. Unknown ref — expect 200, credited=False, and a
        #    CRITICAL log line in the backend.
        bad_payload = {
            "event": "charge.completed",
            "data": {
                "id": _unique_event_id("test-event-bad"),
                "tx_ref": "mock_does_not_exist",
                "amount": 100.00,
                "currency": va["currency"],
                "status": "successful",
            },
        }
        r = c.post("/webhooks/flutterwave", json=bad_payload)
        _print("Webhook (unknown ref, expect credited=False)", r)


if __name__ == "__main__":
    main()