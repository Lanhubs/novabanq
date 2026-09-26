"""Live smoke test for the transactions endpoints.

Hits the running server as the two demo users and prints the
responses for inspection. Not a pytest file — this is a manual script
you run once and read the output of.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * The demo users seeded (python -m scripts.seed_demo_users)

Run:
    python -m scripts.test_transactions_endpoints
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

SENDER_EMAIL = os.environ.get(
    "TEST_SENDER_EMAIL", "codewithkakes@gmail.com"
)
RECIPIENT_EMAIL = os.environ.get(
    "TEST_RECIPIENT_EMAIL", "code2withkakes@gmail.com"
)
OUTSIDER_EMAIL = "realhomeasy@gmail.com"


def _sign_in(email: str, web_api_key: str) -> dict:
    r = httpx.post(
        FIREBASE_SIGNIN_URL,
        params={"key": web_api_key},
        json={
            "email": email,
            "password": PASSWORD,
            "returnSecureToken": True,
        },
        timeout=15.0,
    )
    r.raise_for_status()
    payload = r.json()
    return {"uid": payload["localId"], "id_token": payload["idToken"]}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _print(label: str, response: httpx.Response) -> None:
    print(f"\n=== {label} ===")
    print(f"status: {response.status_code}")
    print(response.json())


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    sender = _sign_in(SENDER_EMAIL, web_api_key)
    recipient = _sign_in(RECIPIENT_EMAIL, web_api_key)
    outsider = _sign_in(OUTSIDER_EMAIL, web_api_key)

    print(f"Sender:    {sender['uid']} ({SENDER_EMAIL})")
    print(f"Recipient: {recipient['uid']} ({RECIPIENT_EMAIL})")
    print(f"Outsider:  {outsider['uid']} ({OUTSIDER_EMAIL})")

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=30.0) as c:
        # Sender's history: expect OUTBOUND transfers + INBOUND funding
        r = c.get("/transactions", headers=_headers(sender["id_token"]))
        _print("Sender's transactions", r)
        sender_items = r.json()["data"]["items"]

        # Recipient's history: expect INBOUND transfers only
        r = c.get("/transactions", headers=_headers(recipient["id_token"]))
        _print("Recipient's transactions", r)

        # Receipt as sender
        if sender_items:
            txn_id = sender_items[0]["transaction_id"]
            r = c.get(
                f"/transactions/{txn_id}",
                headers=_headers(sender["id_token"]),
            )
            _print(f"Sender receipt for {txn_id}", r)

            r = c.get(
                f"/transactions/{txn_id}",
                headers=_headers(recipient["id_token"]),
            )
            _print(f"Recipient receipt for {txn_id}", r)

            r = c.get(
                f"/transactions/{txn_id}",
                headers=_headers(outsider["id_token"]),
            )
            _print(f"Outsider receipt for {txn_id} (expect 404)", r)

        # Nonexistent transaction id
        r = c.get(
            "/transactions/00000000-0000-0000-0000-000000000000",
            headers=_headers(sender["id_token"]),
        )
        _print("Nonexistent transaction (expect 404)", r)


if __name__ == "__main__":
    main()