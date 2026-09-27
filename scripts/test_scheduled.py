"""Live smoke test for the scheduled-transfer endpoints.

Signs in as the demo sender, schedules a transfer for 2 minutes from
now, lists the caller's schedules to confirm it's there, then polls
the schedule until the scheduler fires it and the status flips to a
terminal state.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * The scheduler running in another terminal
      (``python -m scripts.run_scheduler``)
    * The demo sender seeded and funded, with credentials in
      TEST_SENDER_EMAIL / TEST_SENDER_PASSWORD (falls back to a
      placeholder that will not resolve to a real account — set the
      env vars to actually run this against a seeded sender)
    * The composite indexes on ``scheduled_transfers`` created in
      Firestore: (status ASC, execute_at ASC) and (uid ASC,
      created_at DESC)

Run:
    python -m scripts.test_scheduled
"""

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

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
RECIPIENT_TAG = "chidera.ng"
PIN = "48392"


def _sign_in(email: str, password: str, web_api_key: str) -> dict:
    """Sign in via the Firebase Identity Toolkit REST API.

    Raises:
        SystemExit: If sign-in fails. Firebase's own error message
            (e.g. ``EMAIL_NOT_FOUND``, ``INVALID_PASSWORD``) is
            surfaced directly — that message is the entire reason to
            use this endpoint instead of a generic HTTP status code.
    """
    try:
        response = httpx.post(
            FIREBASE_SIGNIN_URL,
            params={"key": web_api_key},
            json={
                "email": email,
                "password": password,
                "returnSecureToken": True,
            },
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()["error"]["message"]
        except (ValueError, KeyError):
            detail = exc.response.text
        raise SystemExit(
            f"Firebase sign-in failed for {email!r}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise SystemExit(f"Could not reach Firebase to sign in: {exc}") from exc

    payload = response.json()
    return {"uid": payload["localId"], "id_token": payload["idToken"]}


def _print(label: str, response: httpx.Response) -> dict | None:
    """Print a labelled response and return its parsed JSON, or None.

    Returns None for non-2xx responses or bodies whose ``data`` is
    absent, so callers can branch on the return value without
    crashing on an error envelope.
    """
    print(f"\n=== {label} ===")
    print(f"status: {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        print(f"non-JSON body: {response.text!r}")
        return None
    print(body)
    if response.status_code < 200 or response.status_code >= 300:
        return None
    if not isinstance(body, dict) or "data" not in body:
        return None
    return body


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    sender = _sign_in(SENDER_EMAIL, SENDER_PASSWORD, web_api_key)
    headers = {"Authorization": f"Bearer {sender['id_token']}"}

    # 2 minutes out. The scheduler polls every 30 seconds, so it
    # should fire within ~2.5 minutes.
    execute_at = datetime.now(timezone.utc) + timedelta(minutes=2)

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=30.0) as c:
        # 1. Create the schedule
        payload = {
            "recipient_tag": RECIPIENT_TAG,
            "amount_minor": 50000,
            "idempotency_key": f"test-sched-{uuid.uuid4().hex}",
            "pin": PIN,
            "execute_at": execute_at.isoformat(),
        }
        r = c.post("/transfers/scheduled", headers=headers, json=payload)
        body = _print("Schedule transfer", r)
        if body is None:
            print("\nFailed to schedule. Aborting.")
            sys.exit(1)

        scheduled_id = body["data"]["scheduled_transfer_id"]
        print(f"\nScheduled for {execute_at.isoformat()}")
        print(f"Scheduled transfer id: {scheduled_id}")

        # 2. List to confirm it's there
        r = c.get("/transfers/scheduled", headers=headers)
        _print("List scheduled transfers", r)

        # 3. Poll for terminal state. Every 15 seconds, up to 4
        #    minutes total.
        print("\nWaiting for scheduler to fire...")
        terminal = {"SETTLED", "FAILED", "CANCELLED"}
        for attempt in range(16):
            time.sleep(15)

            try:
                r = c.get(
                    f"/transfers/scheduled/{scheduled_id}", headers=headers
                )
            except httpx.HTTPError as exc:
                print(f"  attempt {attempt + 1:2d}: request failed: {exc}")
                continue

            if r.status_code != 200:
                print(
                    f"  attempt {attempt + 1:2d}: HTTP {r.status_code} "
                    f"on poll; retrying."
                )
                continue

            body = r.json()
            data = body.get("data") if isinstance(body, dict) else None
            if not data or "status" not in data:
                print(
                    f"  attempt {attempt + 1:2d}: unexpected response "
                    f"shape; retrying."
                )
                continue

            status = data["status"]
            print(f"  attempt {attempt + 1:2d}: status = {status}")
            if status in terminal:
                _print("Final state", r)
                if status == "SETTLED":
                    print("\nSUCCESS: transfer settled via scheduler.")
                    sys.exit(0)
                print(f"\nTransfer ended as {status}. Check logs.")
                sys.exit(1)

        print("\nTimed out after 4 minutes. Check the scheduler terminal.")
        sys.exit(1)


if __name__ == "__main__":
    main()