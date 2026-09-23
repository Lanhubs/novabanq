# NovaBanq Backend API

Backend API for the NovaBanq mobile app, a pan-African payments platform.

| Resource | Link |
| --- | --- |
| Live API | https://novabanq-api.onrender.com |
| Interactive docs (Swagger) | https://novabanq-api.onrender.com/docs |
| Health check | https://novabanq-api.onrender.com/health |

---

## Table of Contents

1. [Quick Start for Frontend](#1-quick-start-for-frontend)
2. [Authentication](#2-authentication)
3. [Response Envelope](#3-response-envelope)
4. [HTTP Status Codes](#4-http-status-codes)
5. [Error Codes](#5-error-codes)
6. [Onboarding Flow](#6-onboarding-flow)
7. [Endpoint Reference](#7-endpoint-reference)
8. [Phone Verification (Firebase Phone Auth)](#8-phone-verification-firebase-phone-auth)
9. [Testing and Integration](#9-testing-and-integration)
10. [What Is Real vs Mocked](#10-what-is-real-vs-mocked)
11. [Project Structure](#11-project-structure)
12. [Local Backend Setup](#12-local-backend-setup)
13. [Running Tests](#13-running-tests)
14. [Support](#14-support)

---

## 1. Quick Start for Frontend

**Base URL**

```text
https://novabanq-api.onrender.com/api/v1
```

All endpoint paths in this document are relative to the base URL. For example, `POST /users/me` means `POST https://novabanq-api.onrender.com/api/v1/users/me`.

**Minimum you need to integrate**

1. Sign users up and in with the Firebase client SDK.
2. Send the Firebase ID token in the `Authorization` header on every request.
3. Parse every response with one shared handler (see [Response Envelope](#3-response-envelope)).
4. Branch on `error.code`, never on `error.message` (see [Error Codes](#5-error-codes)).

---

## 2. Authentication

Every protected endpoint requires a valid **Firebase ID token**:

```http
Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

**Getting the token in Flutter**

```dart
final user = FirebaseAuth.instance.currentUser;
final token = await user?.getIdToken();
```

> **Note:** Firebase ID tokens expire after **1 hour**. Call `getIdToken()` immediately before each API request instead of caching the string. The Firebase SDK refreshes tokens automatically.

The backend verifies the token with Firebase on every request. A missing, expired, or invalid token returns `401` with error code `AUTH_REQUIRED` or `AUTH_INVALID`.

---

## 3. Response Envelope

Every response, success or failure, uses the same shape.

**Success**

```json
{
  "success": true,
  "data": { },
  "error": null
}
```

**Error**

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description.",
    "details": {}
  }
}
```

> **Recommendation:** Build a single global response handler in the Flutter app that checks `success`, then returns either `data` or a typed `error`.

---

## 4. HTTP Status Codes

| Status | Meaning | Typical context |
| --- | --- | --- |
| `200` | OK | Successful request |
| `201` | Created | Profile or PIN created |
| `400` | Bad Request | Malformed JSON or invalid request body |
| `401` | Unauthorized | Missing, invalid, or expired token |
| `403` | Forbidden | Authenticated but not permitted (e.g. email not verified) |
| `404` | Not Found | Resource does not exist (e.g. no user profile) |
| `409` | Conflict | Already exists (e.g. tag taken, PIN already set) |
| `422` | Unprocessable Entity | Validation failure or business rule violation |
| `429` | Too Many Requests | Rate limited (e.g. PIN locked, OTP cooldown active) |
| `500` | Internal Error | Server-side exception |

---

## 5. Error Codes

Switch app logic on `error.code`. Do not rely on `error.message` for business decisions.

| Error code | Meaning | Recommended client action |
| --- | --- | --- |
| `AUTH_REQUIRED` | Authorization header missing | Redirect to login |
| `AUTH_INVALID` | Token invalid or expired | Refresh token via Firebase SDK, then retry |
| `USER_NOT_FOUND` | No profile linked to this Firebase UID | Send user to profile creation |
| `USER_ALREADY_EXISTS` | Profile already exists | Send user to home/dashboard |
| `EMAIL_NOT_VERIFIED` | Email OTP step not completed | Send user to email verification screen |
| `VALIDATION_ERROR` | Request payload failed validation | Highlight the affected fields |
| `TAG_TAKEN` | Requested `@tag` is unavailable | Ask user to choose another tag |
| `TAG_INVALID` | Tag format rules failed | Show the tag format requirements |
| `OTP_INVALID` | Wrong or stale OTP | Ask user to re-enter the code |
| `OTP_EXPIRED` | OTP has expired | Offer to send a new code |
| `OTP_TOO_MANY_ATTEMPTS` | Maximum verification attempts reached | Force a new code request |
| `OTP_RESEND_TOO_SOON` | Resend requested inside cooldown window | Disable the button and show a countdown |
| `PIN_ALREADY_SET` | Transaction PIN already exists | Route to PIN verify or reset |
| `PIN_INVALID` | PIN is incorrect, or no PIN has been set | Ask user to re-enter the PIN |
| `PIN_LOCKED` | Too many failed PIN attempts | Block PIN input and show a lockout countdown |
| `EMAIL_DELIVERY_FAILED` | Outbound email failed to send | Show an inline retry control |
| `PHONE_MISMATCH` | The phone in the token does not match the profile | Show a "phone doesn't match" error |
| `IDENTITY_VERIFICATION_FAILED` | BVN or face verification rejected | Show retry, or contact support |
| `IDENTITY_ALREADY_VERIFIED` | Identity already verified, names locked | Route to dashboard |
| `IDENTITY_PROVIDER_UNAVAILABLE` | KYC provider is down | Show retry later message |
| `INTERNAL_ERROR` | Unhandled backend exception | Show a generic error notice and log it |

---

## 6. Onboarding Flow

Follow this order. Steps 5 to 7 (tag, PIN) are the same for both sign-up methods; only the email OTP steps differ.

```text
Email + password registration
-----------------------------
1. Firebase client: createUserWithEmailAndPassword(email, password)
2. POST /otp/email/send        -> 200 OK
3. User enters the code from their email
4. POST /otp/email/verify      -> 200 OK
5. POST /users/me              -> 201 Created (creates profile + account_number)
6. POST /users/me/tag          -> 200 OK      (claims the @tag)
7. POST /users/me/pin          -> 201 Created (sets the 5-digit PIN)
8. Navigate to the home screen


Google sign-in registration
---------------------------
1. Firebase client: signInWithCredential(...)
2. POST /users/me              -> 201 Created (email OTP is skipped)
3. POST /users/me/tag          -> 200 OK
4. POST /users/me/pin          -> 201 Created
5. Navigate to the home screen
```

> **UI guidance (Google sign-in):** At the profile step, always ask the user to enter or confirm their First, Middle, and Last name manually. Legal names must match their identity documents for KYC.

> **Phone verification is not part of onboarding.** It happens later, from the dashboard. See [Section 8](#8-phone-verification-firebase-phone-auth).

---

## 7. Endpoint Reference

All requests below require `Authorization: Bearer <token>`.

### 7.1 Onboarding endpoints

#### Step 1: Sign up (client-side only)

Call `createUserWithEmailAndPassword(email, password)` with the Firebase SDK. No backend call is needed.

#### Step 2: Send email verification OTP

```http
POST /otp/email/send
```

Request body: `{}`

The recipient address comes from the Firebase session. **Do not send an email in the payload.**

Response:

```json
{
  "success": true,
  "data": {
    "sent": true,
    "expires_in_seconds": 600,
    "resend_available_in_seconds": 10
  },
  "error": null
}
```

Use `resend_available_in_seconds` to drive the resend button countdown.

#### Step 3: Verify email OTP

```http
POST /otp/email/verify
```

```json
{
  "code": "123456"
}
```

Response:

```json
{
  "success": true,
  "data": { "verified": true },
  "error": null
}
```

#### Step 4: Create profile

```http
POST /users/me
```

```json
{
  "first_name": "David",
  "middle_name": "Chukwuemeka",
  "last_name": "Okafor",
  "country": "NG",
  "phone": "+2348012345678"
}
```

Response (`201 Created`):

```json
{
  "success": true,
  "data": {
    "uid": "WPg41qswdZbxSe1X5McIYJlbEn92",
    "first_name": "David",
    "middle_name": "Chukwuemeka",
    "last_name": "Okafor",
    "tag": null,
    "country": "NG",
    "currency": "NGN",
    "phone": "+2348012345678",
    "email": "user@example.com",
    "email_verified": true,
    "phone_verified": false,
    "identity_verified": false,
    "account_number": "0172094612",
    "pin_set": false,
    "avatar_url": null,
    "created_at": "2026-09-23T15:04:44.12Z"
  },
  "error": null
}
```

> Returns `403 EMAIL_NOT_VERIFIED` if Step 3 was skipped. Google sign-in users are exempt and can call this endpoint directly.

#### Tag format: base name + country suffix

Tags are not stored raw. The user only ever types the **base name** (e.g. `david323`); the backend appends a country suffix derived from the profile's `country` field (e.g. `.ng`, `.gh`) to produce the full tag (`david323.ng`).

* The suffix is **not editable** by the user — it's derived server-side from their profile country, never sent by the client.
* **Frontend guidance:** show a live preview under the tag input as the user types, e.g. "Your tag will be `@david323.ng`".
* When a **sender** enters a tag to pay someone, they must enter the **full suffixed tag** (`david323.ng`), not just the base name — the backend does not guess the suffix for lookups initiated by someone else.

#### Check tag availability

```http
GET /users/me/tag/check?tag=david323
```

Pass the base name (no suffix) as the `tag` query parameter.

Response:

```json
{
  "success": true,
  "data": {
    "tag": "david323.ng",
    "available": true
  },
  "error": null
}
```

* **Read-only** — checking availability does **not** reserve the tag. A tag can still be taken by someone else between the check and the actual claim.
* The returned `tag` is already suffixed (the suffix is appended server-side from the caller's profile `country`), so use it directly for the live preview.
* **Frontend guidance:** debounce calls to this endpoint (e.g. 300–500ms after the user stops typing) rather than firing one per keystroke.

#### Step 5: Claim `@tag`

```http
POST /users/me/tag
```

```json
{
  "tag": "david"
}
```

* Allowed characters: `^[a-z0-9_]+$`. Input is lowercased automatically.
* Send only the base name — the server appends the country suffix; do not include it in the request.
* Returns the updated profile object.
* Possible errors: `TAG_TAKEN`, `TAG_INVALID`.

#### Step 6: Set transaction PIN

```http
POST /users/me/pin
```

```json
{
  "pin": "48392"
}
```

Response (`201 Created`):

```json
{
  "success": true,
  "data": { "pin_set": true },
  "error": null
}
```

* Must be exactly **5 digits**.
* Sequential or repeating PINs (e.g. `11111`) are rejected.
* Returns `PIN_ALREADY_SET` if a PIN already exists.

### 7.2 PIN and profile endpoints

#### Verify PIN (gate before transactions)

```http
POST /users/me/pin/verify
```

```json
{
  "pin": "48392"
}
```

Response (`200 OK`):

```json
{
  "success": true,
  "data": { "verified": true },
  "error": null
}
```

Errors:

| Status | Code | Meaning |
| --- | --- | --- |
| `422` | `PIN_INVALID` | Wrong PIN, or no PIN has been set on the account |
| `429` | `PIN_LOCKED` | Too many failed attempts, locked for 20 minutes |
| `404` | `USER_NOT_FOUND` | No profile exists for this user |
| `401` | `AUTH_REQUIRED` / `AUTH_INVALID` | Token missing, invalid, or expired |

After **5 consecutive wrong attempts** the PIN locks for **20 minutes** and the API returns `429 PIN_LOCKED`. Block PIN entry in the UI and show a countdown.

#### Reset transaction PIN

```http
POST /users/me/pin/reset
```

Requires a fresh Firebase ID token that contains a `phone_number` claim, which means the user must have just completed Firebase Phone Auth (see [Section 8](#8-phone-verification-firebase-phone-auth)).

This endpoint takes **no request body**. Verification happens entirely through the token.

```http
POST /users/me/pin/reset
Authorization: Bearer <fresh_token_with_phone_claim>
```

Response (`200 OK`):

```json
{
  "success": true,
  "data": {
    "reset": true,
    "message": "PIN cleared. You may now set a new PIN."
  },
  "error": null
}
```

Errors:

| Status | Code | Meaning |
| --- | --- | --- |
| `422` | `PHONE_MISMATCH` | Token has no `phone_number` claim, or it does not match the phone stored on the profile |
| `404` | `USER_NOT_FOUND` | No profile exists for this user |
| `401` | `AUTH_REQUIRED` / `AUTH_INVALID` | Token missing, invalid, or expired |

**Reset flow:** complete Firebase Phone Auth (link the phone and force-refresh the token, as in Section 8.2), call `POST /users/me/pin/reset`, then call `POST /users/me/pin` with the new PIN in the body (`{"pin": "48392"}`), which returns `201` with `{"pin_set": true}`.

#### Get profile

```http
GET /users/me
```

Returns the profile object shown in Step 4.

#### Update legal name

```http
PATCH /users/me/names
```

```json
{
  "first_name": "David",
  "middle_name": "Chukwuemeka",
  "last_name": "Okafor"
}
```

Allowed only **before** identity verification is completed.

#### Verify phone number

```http
POST /users/me/phone/verify
```

See [Section 8](#8-phone-verification-firebase-phone-auth) for the full flow.

---

## 8. Phone Verification (Firebase Phone Auth)

Phone verification works differently from email OTP. **The backend does not send SMS or generate codes.** Firebase does both. The backend only verifies the resulting token.

### 8.1 Flow

1. The Flutter app calls Firebase `verifyPhoneNumber()`. Firebase sends the SMS.
2. The user enters the SMS code in the app.
3. Firebase verifies the code. The user's fresh ID token now includes a `phone_number` claim.
4. The app sends that fresh token to `POST /users/me/phone/verify`.
5. The backend reads `phone_number` from the token, compares it with the phone stored on the profile, and sets `phone_verified: true`.

### 8.2 Flutter example

```dart
// 1. Send the SMS
await FirebaseAuth.instance.verifyPhoneNumber(
  phoneNumber: userPhone,
  verificationCompleted: (credential) async {
    // Android auto-retrieval path
    await FirebaseAuth.instance.currentUser?.linkWithCredential(credential);
  },
  codeSent: (verificationId, resendToken) {
    // Show the OTP input screen
  },
  verificationFailed: (e) {
    // Handle error (on Android this is usually a missing SHA fingerprint)
  },
  codeAutoRetrievalTimeout: (verificationId) {},
);

// 2. After the user enters the code, link the phone to the signed-in account
final credential = PhoneAuthProvider.credential(
  verificationId: verificationId,
  smsCode: enteredCode,
);
await FirebaseAuth.instance.currentUser?.linkWithCredential(credential);

// 3. Force-refresh the token so it includes the phone_number claim
final token = await FirebaseAuth.instance.currentUser?.getIdToken(true);

// 4. Send it to the backend
// POST /api/v1/users/me/phone/verify
// Header: Authorization: Bearer <token>
// Body:   { "phone_number": "+2348012345678" }
```

> **Important:** Use `linkWithCredential` on the current user rather than `signInWithCredential`. Signing in with a phone credential while already signed in with email or Google switches the session to a different Firebase account, and the token's UID will no longer match the user's NovaBanq profile.

### 8.3 Backend endpoint

```http
POST /users/me/phone/verify
Authorization: Bearer <fresh_token_with_phone_claim>
Content-Type: application/json
```

```json
{
  "phone_number": "+2348012345678"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "verified": true,
    "phone_number": "+2348012345678"
  },
  "error": null
}
```

If the token's `phone_number` claim does not match the phone stored on the profile, the request returns `422` with code `PHONE_MISMATCH`.

### 8.4 Firebase Console setup (required)

Ask whoever owns the Firebase project to confirm all of the following before you start:

1. **Phone sign-in enabled:** Firebase Console → Authentication → Sign-in method → Phone → Enable.
2. **Android SHA-1 and SHA-256 fingerprints registered:** Firebase Console → Project Settings → Your apps → Add fingerprint. Missing fingerprints cause `verificationFailed` errors on Android.
3. **APNs configured (iOS only):** required for silent push on iOS.

### 8.5 Testing without real SMS

Firebase supports **test phone numbers**: fictional numbers with a fixed code. No SMS is sent, and the pre-set code is accepted.

**Setup**

1. Firebase Console → Authentication → Sign-in method → Phone → expand **Phone numbers for testing**.
2. Add a number (e.g. `+2348012345678`) and a code (e.g. `123456`).
3. Save.

**At runtime**, the app calls `verifyPhoneNumber()` with the test number. No SMS goes out, `codeSent` fires, and the tester enters the pre-set code. Firebase then issues a token identical to a real one.

> **Do not add a backend bypass endpoint for testing.** Firebase test numbers keep the production auth flow intact and only skip SMS delivery. The backend never needs to know the difference.

### 8.6 Phone verification is a soft gate

Phone verification happens **on the dashboard after signup**, not during onboarding. Users can browse the app before verifying. Transfers will require `phone_verified: true` once that feature ships.

---

## 9. Testing and Integration

### 9.1 Swagger UI

Open https://novabanq-api.onrender.com/docs to test endpoints manually.

1. Generate a valid user token (via the client SDK, or the terminal command below).
2. Click **Authorize** (top right).
3. Paste the token and confirm.

### 9.2 Generate a test token from the terminal

```bash
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=YOUR_FIREBASE_WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@novabanq.dev","password":"test1234","returnSecureToken":true}'
```

Copy `idToken` from the response and use it as the Bearer token.

---

## 10. What Is Real vs Mocked

Current scope is a hackathon build.

| Feature | Status | Details |
| --- | --- | --- |
| Firebase Authentication | Production-ready | Fully integrated |
| Firestore database | Production-ready | Real persistence |
| Email OTP | Production-ready | Sent via Brevo |
| Phone verification | Production-ready | Firebase native SMS |
| BVN / identity check | Mock | Passes on regex format check only |
| Biometric face sync | Mock | Returns deterministic positive responses |
| Account numbers | Placeholder | 10-digit NovaBanq-internal numbers. Not real bank accounts — will be replaced with real NUBANs once virtual accounts go live via Flutterwave. |
| Virtual accounts (Flutterwave) | Not yet implemented | — |
| Ledger / transfer engine | Under construction | Planned for a future build |
| Wallet balances | Under construction | Planned for a future build |

---

## 11. Project Structure

```text
app/
├── main.py                  FastAPI app initialization
├── api/                     Route aggregation and versioning
├── core/                    Config, security handlers, exceptions
├── infra/                   Third-party adapters (Firebase, Firestore, Brevo, Flutterwave)
└── features/                Domain-driven feature modules
    ├── users/               Profile, identity claims, transaction PIN
    ├── otp/                 Email verification delivery
    ├── tags/                Unique @tag handles
    ├── account_numbers/     Account number generation
    ├── identity/            Government ID / BVN validation (mocked)
    ├── virtual_accounts/    Payment gateway bridge (Flutterwave sandbox)
    ├── accounts/            Balances (planned)
    ├── funding/             Inbound deposits (planned)
    ├── currency/            FX calculations (planned)
    ├── ledger/              Double-entry bookkeeping (planned)
    ├── transfers/           Outbound transactions (planned)
    └── transactions/        History and statements (planned)
```

Each feature module has four layers:

| File | Responsibility |
| --- | --- |
| `router.py` | API routes (controllers) |
| `schemas.py` | Pydantic request/response models |
| `service.py` | Business logic |
| `repository.py` | Firestore access |

---

## 12. Local Backend Setup

```bash
# Create a virtual environment
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate it (macOS/Linux)
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the dev server
uvicorn app.main:app --reload
```

**Prerequisites**

* A valid `serviceAccountKey.json` in the project root.
* A `.env` file configured from `.env.example`.

---

## 13. Running Tests

```bash
pytest tests/ -v -s
```

`tests/test_auth.py` runs integration tests against a live local server connected to Firebase and Firestore. Set `FIREBASE_WEB_API_KEY` in your local `.env` first.

---

## 14. Support

* **API specs and contracts:** contact the primary backend engineer.
* **Authentication platform:** check the project's Firebase Console settings.