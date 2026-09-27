"""Live smoke test for the AI intent endpoint.

Signs in as the demo sender, fires a handful of natural-language
instructions at the parse endpoint, and prints the structured
response for each.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * GEMINI_API_KEY set in .env (read by the running server, not by
      this script)
    * FIREBASE_WEB_API_KEY set in .env
    * The demo sender seeded, with credentials in TEST_SENDER_EMAIL /
      TEST_SENDER_PASSWORD (falls back to a placeholder that will not
      resolve to a real account — set the env vars to actually run
      this against a seeded sender)

Run:
    python -m scripts.test_ai_intent
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

# A handful of phrasings the parser should handle, plus one that
# should fail cleanly ("hello").
TEST_INPUTS = [
    "send 5000 to olanrewaju.ng",
    "help me transfer 500 cedis to davidkampe.gh",
    "send 1000 to david.ng at 5pm",
    "hello there",
]


def _sign_in(email: str, password: str, web_api_key: str) -> dict[str, str]:
    """Sign in via the Firebase Identity Toolkit REST API.

    Raises:
        SystemExit: If sign-in fails. Firebase's own error message
            (e.g. ``"EMAIL_NOT_FOUND"``, ``"INVALID_PASSWORD"``) is
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


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    sender = _sign_in(SENDER_EMAIL, SENDER_PASSWORD, web_api_key)
    headers = {"Authorization": f"Bearer {sender['id_token']}"}

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=120.0) as client:
        for text in TEST_INPUTS:
            print(f"\n=== Input: {text!r} ===")

            try:
                response = client.post(
                    "/ai/parse-transfer", headers=headers, json={"text": text}
                )
            except httpx.HTTPError as exc:
                # A downed server or network hiccup shouldn't stop the
                # rest of the smoke test from running.
                print(f"request failed: {exc}")
                continue

            print(f"status: {response.status_code}")
            try:
                print(response.json())
            except ValueError:
                print(f"non-JSON response body: {response.text!r}")


if __name__ == "__main__":
    main()