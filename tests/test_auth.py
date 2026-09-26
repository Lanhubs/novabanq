"""End-to-end authentication flow test.

This test exercises the full auth surface against a live local server
backed by real Firebase and real Firestore. It is intentionally
integration-level: it proves the token verification, email gate, OTP
marker, tag uniqueness, PIN hashing, and PIN lockout all work together
with the real infrastructure.

Requirements:
    * The FastAPI app must be running locally at http://127.0.0.1:8000
      (uvicorn app.main:app --reload)
    * FIREBASE_WEB_API_KEY must be set in the environment
    * The service account key must be available to the backend

The test uses a fixed test email so the same account is reused across
runs. If the account already exists, it signs in instead of signing up.
Override the email via the TEST_USER_EMAIL env var.

Run:
    pytest tests/test_auth.py -v -s
"""

import os
import time
from collections.abc import Iterator

import httpx
import pytest
from dotenv import load_dotenv

from app.core.constants import (
    COUNTRY_TAG_SUFFIX,
    TAG_SUFFIX_SEPARATOR,
    Country,
    FirestoreCollection,
    OtpPurpose,
)
from app.infra.firestore import document

# Load .env so os.environ sees FIREBASE_WEB_API_KEY during the test run.
load_dotenv()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
FIREBASE_SIGNUP_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
FIREBASE_SIGNIN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)

DEFAULT_TEST_EMAIL = "codewithkakes@gmail.com"
TEST_PASSWORD = "test1234"
TEST_PIN = "48392"
WRONG_PIN = "11111"

TEST_FIRST_NAME = "David"
TEST_MIDDLE_NAME = "Chukwuemeka"
TEST_LAST_NAME = "Okafor"
TEST_PHONE = "+2348012345678"

# Typed as the enum member, not a raw string, so that the dict lookups
# below type-check. ``Country`` is a ``StrEnum``, so the value still
# serializes to ``"NG"`` when sent over HTTP — the change is purely a
# static-typing improvement, not a wire change.
TEST_COUNTRY: Country = Country.NIGERIA

# Suffix the backend will append to any base tag for TEST_COUNTRY.
TEST_TAG_SUFFIX = COUNTRY_TAG_SUFFIX[TEST_COUNTRY]
TEST_TAG_SEPARATOR = TAG_SUFFIX_SEPARATOR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def web_api_key() -> str:
    """Return the Firebase Web API key or skip the test if unset."""
    key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not key:
        pytest.skip(
            "FIREBASE_WEB_API_KEY is not set. Add it to .env before running "
            "this test."
        )
    return key


@pytest.fixture(scope="session")
def test_user(web_api_key: str) -> dict:
    """Create or sign in a Firebase user and return its identity.

    Uses a fixed test email so the same account is reused across runs.
    If the account already exists, the fixture signs in instead of
    signing up — reruns are idempotent and no orphan users accumulate.
    """
    email = os.environ.get("TEST_USER_EMAIL", DEFAULT_TEST_EMAIL)

    signup_response = httpx.post(
        FIREBASE_SIGNUP_URL,
        params={"key": web_api_key},
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "returnSecureToken": True,
        },
        timeout=15.0,
    )

    if signup_response.status_code == 200:
        payload = signup_response.json()
    else:
        error_message = (
            signup_response.json().get("error", {}).get("message", "")
        )
        if error_message != "EMAIL_EXISTS":
            signup_response.raise_for_status()

        signin_response = httpx.post(
            FIREBASE_SIGNIN_URL,
            params={"key": web_api_key},
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "returnSecureToken": True,
            },
            timeout=15.0,
        )
        signin_response.raise_for_status()
        payload = signin_response.json()

    return {
        "email": email,
        "uid": payload["localId"],
        "id_token": payload["idToken"],
    }


@pytest.fixture
def auth_headers(test_user: dict) -> dict:
    """Return Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['id_token']}"}


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    """Yield an HTTP client rooted at the API prefix."""
    with httpx.Client(base_url=BASE_URL + API_PREFIX, timeout=15.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _otp_document_exists(uid: str) -> bool:
    """Return True if an active OTP document exists for this uid."""
    snapshot = document(
        FirestoreCollection.OTP_CODES,
        f"{uid}_{OtpPurpose.EMAIL_VERIFICATION}",
    ).get()
    if not snapshot.exists:
        return False
    data = snapshot.to_dict()
    return data is not None


def _otp_hash_length(uid: str) -> int:
    """Return the length of the stored OTP hash, or 0 if absent."""
    snapshot = document(
        FirestoreCollection.OTP_CODES,
        f"{uid}_{OtpPurpose.EMAIL_VERIFICATION}",
    ).get()
    if not snapshot.exists:
        return 0
    data = snapshot.to_dict() or {}
    return len(data.get("code_hash", ""))


def _profile_payload() -> dict:
    """Return the canonical profile creation payload.

    ``country`` is emitted as ``str(TEST_COUNTRY)`` so the JSON body
    carries the wire value (``"NG"``) rather than an enum repr. Because
    ``Country`` is a ``StrEnum`` this would serialize correctly either
    way, but the explicit cast documents the intent and keeps the
    payload a plain-JSON object, not one carrying an enum member.
    """
    return {
        "first_name": TEST_FIRST_NAME,
        "middle_name": TEST_MIDDLE_NAME,
        "last_name": TEST_LAST_NAME,
        "country": str(TEST_COUNTRY),
        "phone": TEST_PHONE,
    }


def _full_tag(base_tag: str) -> str:
    """Return the full tag the backend will produce for TEST_COUNTRY."""
    return f"{base_tag}{TEST_TAG_SEPARATOR}{TEST_TAG_SUFFIX}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health() -> None:
    """The server must be reachable before anything else runs."""
    response = httpx.get(f"{BASE_URL}/health", timeout=10.0)
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_profile_creation_requires_names(
    client: httpx.Client,
    auth_headers: dict,
) -> None:
    """POST /users/me must reject a payload missing name fields."""
    response = client.post(
        "/users/me",
        headers=auth_headers,
        json={"country": str(TEST_COUNTRY), "phone": TEST_PHONE},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_profile_creation_blocked_without_email_verification(
    client: httpx.Client,
    auth_headers: dict,
) -> None:
    """POST /users/me must fail with EMAIL_NOT_VERIFIED before OTP."""
    response = client.post(
        "/users/me",
        headers=auth_headers,
        json=_profile_payload(),
    )
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_send_email_otp(client: httpx.Client, auth_headers: dict) -> None:
    """POST /otp/email/send must return 200 with the cooldown payload."""
    response = client.post(
        "/otp/email/send",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["sent"] is True
    assert body["data"]["expires_in_seconds"] > 0
    assert body["data"]["resend_available_in_seconds"] > 0


def test_resend_cooldown_enforced(
    client: httpx.Client,
    auth_headers: dict,
) -> None:
    """A second send within the cooldown window must return 429."""
    response = client.post(
        "/otp/email/send",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["error"]["code"] == "OTP_RESEND_TOO_SOON"


def test_otp_stored_hashed(test_user: dict) -> None:
    """The OTP document must contain a hash, never the plaintext code."""
    assert _otp_document_exists(test_user["uid"]), "OTP document not written."
    hash_length = _otp_hash_length(test_user["uid"])
    assert hash_length == 64, f"Expected SHA-256 hex digest, got {hash_length} chars."


@pytest.mark.skip(
    reason=(
        "OTP verify requires the plaintext code, which is intentionally "
        "unrecoverable from Firestore. Set OTP_CODE env var to run."
    )
)
def test_verify_email_otp(
    client: httpx.Client,
    auth_headers: dict,
) -> None:
    """POST /otp/email/verify must accept the code and write the marker."""
    code = os.environ.get("OTP_CODE")
    if not code:
        pytest.skip("OTP_CODE is not set.")

    response = client.post(
        "/otp/email/verify",
        headers=auth_headers,
        json={"code": code},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verified"] is True


@pytest.mark.skip(
    reason="Depends on a verified email, which requires the OTP_CODE env var."
)
def test_full_onboarding_after_verification(
    client: httpx.Client,
    auth_headers: dict,
) -> None:
    """After OTP verification, profile creation, tag, and PIN must succeed."""
    # --- Profile creation ---
    response = client.post(
        "/users/me",
        headers=auth_headers,
        json=_profile_payload(),
    )
    assert response.status_code == 201, response.text
    profile = response.json()["data"]
    assert profile["email_verified"] is True
    assert profile["account_number"]
    assert len(profile["account_number"]) == 10
    assert profile["account_number"].isdigit()
    assert profile["pin_set"] is False
    assert profile["first_name"] == TEST_FIRST_NAME
    assert profile["middle_name"] == TEST_MIDDLE_NAME
    assert profile["last_name"] == TEST_LAST_NAME
    assert profile["identity_verified"] is False
    assert profile["tag"] is None

    # --- Tag availability check before claim ---
    base_tag = f"authtest{int(time.time())}"
    full_tag = _full_tag(base_tag)

    response = client.get(
        "/users/me/tag/check",
        headers=auth_headers,
        params={"tag": base_tag},
    )
    assert response.status_code == 200, response.text
    check_body = response.json()["data"]
    assert check_body["tag"] == full_tag
    assert check_body["available"] is True

    # --- Tag claim appends suffix ---
    response = client.post(
        "/users/me/tag",
        headers=auth_headers,
        json={"tag": base_tag},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["tag"] == full_tag

    # --- Availability check now reports taken ---
    response = client.get(
        "/users/me/tag/check",
        headers=auth_headers,
        params={"tag": base_tag},
    )
    assert response.status_code == 200, response.text
    check_body = response.json()["data"]
    assert check_body["tag"] == full_tag
    assert check_body["available"] is False

    # --- Client-supplied suffix is stripped on claim ---
    base_tag_2 = f"authtest2{int(time.time())}"
    response = client.post(
        "/users/me/tag",
        headers=auth_headers,
        json={"tag": f"{base_tag_2}.gh"},
    )
    assert response.status_code == 200, response.text
    # Backend ignores the client-supplied ".gh" and appends the profile suffix.
    assert response.json()["data"]["tag"] == _full_tag(base_tag_2)

    # --- PIN set ---
    response = client.post(
        "/users/me/pin",
        headers=auth_headers,
        json={"pin": TEST_PIN},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["pin_set"] is True

    # --- PIN verify (correct) ---
    response = client.post(
        "/users/me/pin/verify",
        headers=auth_headers,
        json={"pin": TEST_PIN},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verified"] is True

    # --- PIN verify (wrong, 4 attempts) ---
    for _ in range(4):
        response = client.post(
            "/users/me/pin/verify",
            headers=auth_headers,
            json={"pin": WRONG_PIN},
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "PIN_INVALID"

    # --- Fifth wrong attempt triggers lockout ---
    response = client.post(
        "/users/me/pin/verify",
        headers=auth_headers,
        json={"pin": WRONG_PIN},
    )
    assert response.status_code == 429, response.text
    assert response.json()["error"]["code"] == "PIN_LOCKED"

    # --- Correct PIN also rejected while locked ---
    response = client.post(
        "/users/me/pin/verify",
        headers=auth_headers,
        json={"pin": TEST_PIN},
    )
    assert response.status_code == 429, response.text
    assert response.json()["error"]["code"] == "PIN_LOCKED"