"""Interactive terminal chat with Nova, the NovaBanq AI assistant.

Signs in as the demo sender, then loops: you type a question, the
script posts it to ``POST /ai/ask``, and Nova's answer is printed
back. Type ``exit`` or ``quit`` to stop.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * GEMINI_API_KEY set in .env
    * FIREBASE_WEB_API_KEY set in .env
    * TEST_SENDER_EMAIL / TEST_SENDER_PASSWORD in .env pointing at a
      seeded user

Run:
    python -m scripts.ask_nova
"""

import os
from typing import Any

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


def _sign_in(email: str, password: str, web_api_key: str) -> dict[str, str]:
    """Sign in via the Firebase Identity Toolkit REST API.

    Raises:
        SystemExit: If sign-in fails, with Firebase's own error message
            (e.g. ``EMAIL_NOT_FOUND``, ``INVALID_PASSWORD``) surfaced
            directly, rather than a generic HTTP status.
    """
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


def _print_answer(body: dict[str, Any]) -> None:
    """Pretty-print the AskResponse envelope Nova returned."""
    if not body.get("success"):
        err = body.get("error", {})
        print(
            f"\n  [error] {err.get('code', 'UNKNOWN')}: "
            f"{err.get('message', 'no message')}\n"
        )
        return

    data = body["data"]
    kind = data.get("kind", "?")
    answer = data.get("answer", "")

    print(f"\n  Nova ({kind}):")
    # Wrap the answer at ~70 columns so long replies don't scroll off
    # the terminal. No textwrap import needed for a demo — this is a
    # simple word-wrap that handles the common case.
    words = answer.split()
    line = "    "
    for word in words:
        if len(line) + len(word) + 1 > 74:
            print(line)
            line = "    " + word
        else:
            line = line + (" " if line.strip() else "") + word
    if line.strip():
        print(line)
    print()


def main() -> None:
    web_api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not web_api_key:
        raise SystemExit("FIREBASE_WEB_API_KEY is not set in .env")

    print(f"Signing in as {SENDER_EMAIL} ...")
    sender = _sign_in(SENDER_EMAIL, SENDER_PASSWORD, web_api_key)
    headers = {"Authorization": f"Bearer {sender['id_token']}"}

    print()
    print("=" * 70)
    print("  Nova — your NovaBanq assistant")
    print("  Ask anything about your money. Type 'exit' or 'quit' to stop.")
    print("=" * 70)

    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=60.0) as c:
        while True:
            try:
                question = input("\nyou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                break

            try:
                r = c.post(
                    "/ai/ask",
                    headers=headers,
                    json={"question": question},
                )
            except httpx.HTTPError as exc:
                print(f"\n  [network error] {exc}\n")
                continue

            try:
                body = r.json()
            except ValueError:
                print(f"\n  [non-JSON response] {r.text!r}\n")
                continue

            _print_answer(body)

    print("Goodbye.")


if __name__ == "__main__":
    main()