"""Interactive terminal chat with Nova, the NovaBanq AI assistant.

Signs in as the demo sender, then loops: you type a question, the
script posts it to ``POST /ai/ask``, and Nova's answer is printed
back. Type ``exit`` or ``quit`` to stop.

When Nova recognizes a transfer intent (``data.action ==
"confirm_transfer"``), the script mimics the Flutter app's flow:
it prompts for the PIN (via ``getpass``, so the PIN never echoes to
the terminal), calls ``POST /ai/execute-transfer`` with the
structured fields, and prints the outcome. This makes the script a
faithful end-to-end test of the chat-native transfer flow.

Requires:
    * uvicorn running at http://127.0.0.1:8000
    * GEMINI_API_KEY set in .env
    * FIREBASE_WEB_API_KEY set in .env
    * TEST_SENDER_EMAIL / TEST_SENDER_PASSWORD in .env pointing at a
      seeded user

Run:
    python -m scripts.ask_nova
"""

import getpass
import os
import uuid
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


def _wrap(text: str, indent: str = "    ", width: int = 74) -> None:
    """Print text word-wrapped to the terminal width.

    Simple whitespace-split wrap; good enough for terminal output and
    doesn't need textwrap. Prints one line at a time with the given
    indent prefix.
    """
    words = text.split()
    line = indent
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(line)
            line = indent + word
        else:
            line = line + (" " if line.strip() else "") + word
    if line.strip():
        print(line)


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
    _wrap(answer)
    print()


def _is_transfer_confirmation(body: dict[str, Any]) -> bool:
    """True when the response is a transfer intent ready for a PIN.

    The trigger is ``data.action == "confirm_transfer"`` — NOT
    ``kind == "TRANSFER_INTENT"`` alone. A TRANSFER_INTENT reply with
    a help message (e.g. "Please include an amount…") also has
    ``kind: "TRANSFER_INTENT"`` but ``data: null``, and must not
    trigger the PIN dialog.
    """
    if not body.get("success"):
        return False
    data = body.get("data")
    if not isinstance(data, dict):
        return False
    if data.get("kind") != "TRANSFER_INTENT":
        return False
    inner = data.get("data")
    if not isinstance(inner, dict):
        return False
    return inner.get("action") == "confirm_transfer"


def _print_transfer_result(body: dict[str, Any]) -> None:
    """Pretty-print the /ai/execute-transfer response.

    Handles both the success envelope (IMMEDIATE or SCHEDULED) and the
    error envelope. The error envelope covers PIN_INVALID, PIN_LOCKED,
    INSUFFICIENT_BALANCE, RECIPIENT_CHANGED, and every other
    NovaBanqError that the endpoint can raise.
    """
    if not body.get("success"):
        err = body.get("error", {})
        print(
            f"\n  ✗ Transfer failed — {err.get('code', 'UNKNOWN')}: "
            f"{err.get('message', 'no message')}\n"
        )
        return

    data = body["data"]
    kind = data.get("kind")

    if kind == "IMMEDIATE":
        transfer = data["transfer"]
        tx_id = transfer["transaction_id"]
        recipient = transfer["quote"]["recipient"]["display_name"]
        print(
            f"\n  ✓ Done. Sent to {recipient}. "
            f"Transaction ID: {tx_id}\n"
        )
    elif kind == "SCHEDULED":
        scheduled = data["scheduled_transfer"]
        recipient = scheduled.get("recipient_display_name") or scheduled[
            "recipient_tag"
        ]
        execute_at = scheduled["execute_at"]
        print(
            f"\n  ✓ Scheduled. {recipient} will receive it at "
            f"{execute_at}.\n"
        )
    else:
        print(f"\n  [unexpected kind] {kind}\n")


def _confirm_and_execute(
    client: httpx.Client,
    headers: dict[str, str],
    body: dict[str, Any],
) -> None:
    """Prompt for a PIN and execute the confirmed transfer.

    Mirrors the Flutter flow: the PIN is collected through a dedicated
    secure prompt (``getpass`` here), never typed as chat text. The
    structured fields come straight from the intent block the backend
    returned — the amount and recipient that settle are the amount and
    recipient the user was shown.
    """
    intent = body["data"]["data"]["intent"]

    # Generate a fresh idempotency key for this attempt. A retry with
    # the same key would return the original result; for the demo
    # script, one key per attempt is fine.
    idempotency_key = f"ask-nova-{uuid.uuid4().hex}"

    try:
        pin = getpass.getpass("PIN (hidden) > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled — no transfer was made.\n")
        return

    if not pin:
        print("\n  Cancelled — no transfer was made.\n")
        return

    payload = {
        "recipient_tag": intent["recipient_tag"],
        "amount_minor": intent["amount_minor"],
        "confirmed_recipient_uid": intent["recipient_uid"],
        "idempotency_key": idempotency_key,
        "pin": pin,
        "execute_at": intent.get("execute_at"),
    }

    try:
        r = client.post(
            "/ai/execute-transfer",
            headers=headers,
            json=payload,
        )
    except httpx.HTTPError as exc:
        print(f"\n  [network error] {exc}\n")
        return

    try:
        result = r.json()
    except ValueError:
        print(f"\n  [non-JSON response] {r.text!r}\n")
        return

    _print_transfer_result(result)


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
    print(
        "  Type a transfer instruction (e.g. 'send 500 to david.ng') to"
    )
    print("  test the chat-native send flow — you'll be prompted for a PIN.")
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

            # If this reply is a transfer confirmation, follow up with
            # the PIN prompt and the execute call — the same flow the
            # Flutter app runs. Otherwise just return to the prompt.
            if _is_transfer_confirmation(body):
                _confirm_and_execute(c, headers, body)

    print("Goodbye.")


if __name__ == "__main__":
    main()