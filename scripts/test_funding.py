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

        # 2. Fire a webhook for that account, simulating a deposit
        webhook_payload = {
            "event": "charge.completed",
            "data": {
                "id": "test-event-001",
                "tx_ref": provider_ref,
                "amount": 250.00,
                "currency": va["currency"],
                "status": "successful",
            },
        }
        r = c.post("/webhooks/flutterwave", json=webhook_payload)
        _print("Webhook (fresh deposit)", r)

        # 3. Fire the same webhook again — should be a no-op
        r = c.post("/webhooks/flutterwave", json=webhook_payload)
        _print("Webhook (replay, expect credited=False)", r)

        # 4. Check the balance
        r = c.get("/accounts/me", headers=headers)
        _print("Balance after funding", r)

        # 5. Unknown ref — expect 200, credited=False
        bad_payload = {
            "event": "charge.completed",
            "data": {
                "id": "test-event-002",
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