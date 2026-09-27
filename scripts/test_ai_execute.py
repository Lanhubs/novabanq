"""Live smoke test for the combined AI execute-transfer endpoint.

Signs in as the demo sender, fires a handful of natural-language
instructions at the combined endpoint with a real PIN, and prints
the discriminated response for each.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * The scheduler running in a second terminal
      (``python -m scripts.run_scheduler``) if you want to watch any
      scheduled transfer actually fire
    * GEMINI_API_KEY set in .env
    * FIREBASE_WEB_API_KEY set in .env
    * TEST_SENDER_EMAIL / TEST_SENDER_PASSWORD in .env pointing at a
      seeded, funded user

Run:
    python -m scripts.test_ai_execute
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
SENDER_EMAIL = os.environ.get("TEST_SENDER_EMAIL", "demo.sender@novabanq.test")
SENDER_PASSWORD = os.environ.get("TEST_SENDER_PASSWORD", "test1234")
PIN = "48392"

# A mix of shapes the endpoint should handle:
#   * immediate transfer (no time stated)
#   * scheduled transfer (future time stated)
#   * ambiguous input that should fail cleanly
#   * an instruction with an amount missing
TEST_INPUTS = [
    "send 100 to chidera.ng",
    "send 100 to chidera.ng at 5pm",
    "hello there",
    "send to chidera.ng",
]


def _sign_in(email: str, password: str, web_api_key: str) -> dict:
    try:
        r = httpx.post(
            FIREBASE_SIGNIN_URL,
            params={"key": web_api_key},
            json={
                "email": email,
                "password": password,
                "returnSecureToken": True,
            },
            timeout=15.0,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()["error"]["message"]
        except (ValueError, KeyError):
            detail = exc.response.text
        raise SystemExit(f"Sign-in failed: {detail}") from exc
    except httpx.HTTPError as exc:
        raise SystemExit(f"Could not reach Firebase: {exc}") from exc

    p = r.json()
    return {"uid": p["localId"], "id_token": p["idToken"]}


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    sender = _sign_in(SENDER_EMAIL, SENDER_PASSWORD, web_api_key)
    headers = {"Authorization": f"Bearer {sender['id_token']}"}

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=60.0) as c:
        for text in TEST_INPUTS:
            print(f"\n=== Input: {text!r} ===")
            try:
                r = c.post(
                    "/ai/execute-transfer",
                    headers=headers,
                    json={"text": text, "pin": PIN},
                )
            except httpx.HTTPError as exc:
                print(f"request failed: {exc}")
                continue

            print(f"status: {r.status_code}")
            try:
                body = r.json()
            except ValueError:
                print(f"non-JSON body: {r.text!r}")
                continue
            print(body)

            # Gate on the envelope's own success flag, not a specific
            # HTTP status code. A resource-creating endpoint in this
            # codebase (profile, PIN, and by the same pattern, a new
            # transaction) returns 201 on success, not 200 — checking
            # status_code == 200 here would silently skip the
            # discriminated-response summary below on every real
            # success.
            if body.get("success") and body.get("data"):
                kind = body["data"].get("kind")
                print(f"-> kind: {kind}")

                if kind == "IMMEDIATE":
                    txn = body["data"]["transfer"]["transaction_id"]
                    print(f"   transaction_id: {txn}")
                elif kind == "SCHEDULED":
                    scheduled = body["data"]["scheduled_transfer"]
                    print(
                        f"   scheduled_transfer_id: "
                        f"{scheduled['scheduled_transfer_id']}"
                    )
                    print(f"   execute_at: {scheduled['execute_at']}")


if __name__ == "__main__":
    main()