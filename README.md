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
9. [Identity Verification (KYC)](#9-identity-verification-kyc)
10. [Testing and Integration](#10-testing-and-integration)
11. [What Is Real vs Mocked](#11-what-is-real-vs-mocked)
12. [Project Structure](#12-project-structure)
13. [Local Backend Setup](#13-local-backend-setup)
14. [Running Tests](#14-running-tests)
15. [Support](#15-support)

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
| `201` | Created | Profile, PIN, transfer, or scheduled transfer created |
| `400` | Bad Request | Malformed JSON or invalid request body |
| `401` | Unauthorized | Missing, invalid, or expired token |
| `403` | Forbidden | Authenticated but not permitted (e.g. email not verified) |
| `404` | Not Found | Resource does not exist (e.g. no user profile, no transaction) |
| `409` | Conflict | Already exists, or already settled (e.g. tag taken, PIN already set, duplicate transfer) |
| `422` | Unprocessable Entity | Validation failure or business rule violation |
| `429` | Too Many Requests | Rate limited (e.g. PIN locked, OTP cooldown active) |
| `500` | Internal Error | Server-side exception |
| `502` | Bad Gateway | An upstream provider failed — FX rates, KYC, email, funding, or the AI provider — or a ledger/infrastructure failure occurred |

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
| `IDENTITY_PROVIDER_UNAVAILABLE` | KYC provider, Cloudinary, or the verification repository is down | Show retry later message |
| `INTERNAL_ERROR` | Unhandled backend exception, or an upstream provider failure | Show a generic error notice and log it |
| `RECIPIENT_NOT_FOUND` | The recipient `@tag` does not resolve to any user | Show "no user found with that tag" |
| `SELF_TRANSFER` | Sender and recipient are the same user | Block the transfer client-side before confirming |
| `AMOUNT_INVALID` | Amount below the platform minimum or malformed | Show the minimum amount |
| `CORRIDOR_UNSUPPORTED` | The two currencies have no configured FX corridor | Tell the user this pair isn't supported yet |
| `INSUFFICIENT_BALANCE` | Balance cannot cover the total debit | Show the shortfall amount |
| `DUPLICATE_TRANSFER` | This idempotency key has already settled | Fetch the original result by transaction id — do not retry |
| `RATE_UNAVAILABLE` | FX provider unreachable and the cached rate is too stale | Show a "try again in a moment" message |
| `FX_PROVIDER_UNAVAILABLE` | FX provider rejected the request (auth, quota) | Same message to the user; log the code for backend diagnostics |
| `TRANSACTION_NOT_FOUND` | Transaction id does not exist, or the caller is not on it | Show a "not found" message |
| `SCHEDULED_TRANSFER_NOT_FOUND` | Scheduled-transfer id does not exist, or the caller is not its owner | Show a "not found" message |
| `FUNDING_PROVIDER_UNAVAILABLE` | Flutterwave provider stub reached, or the real provider is down | Show retry later message |

> **A code that does *not* exist:** `INVALID_IDEMPOTENCY_KEY` is not a real value — confirmed directly against `app/core/constants.py`'s `ErrorCode` enum. A malformed idempotency key on `POST /transfers` or `POST /transfers/scheduled` surfaces as `VALIDATION_ERROR` instead. If you see any error-handling code or an older doc referencing `INVALID_IDEMPOTENCY_KEY`, it's stale — fix it to check for `VALIDATION_ERROR`.

---

## 6. Onboarding Flow

Follow this order. Steps 5 to 10 (tag, PIN, identity) are the same for both sign-up methods; only the email OTP steps differ.

```text
Email + password registration
-----------------------------
1.  Firebase client: createUserWithEmailAndPassword(email, password)
2.  POST /otp/email/send             -> 200 OK
3.  User enters the code from their email
4.  POST /otp/email/verify           -> 200 OK
5.  POST /users/me                   -> 201 Created (creates profile + account_number)
6.  POST /users/me/tag               -> 200 OK      (claims the @tag)
7.  POST /users/me/pin               -> 201 Created (sets the 5-digit PIN)
8.  GET  /identity/upload-signature  -> 200 OK      (signed payload)
9.  [Upload selfie directly to Cloudinary]
10. POST /identity/verify            -> 200 OK      (VERIFIED | REJECTED | WATCHLISTED | NOT_FOUND)
11. Navigate to the home screen


Google sign-in registration
---------------------------
1. Firebase client: signInWithCredential(...)
2. POST /users/me                   -> 201 Created (email OTP is skipped)
3. POST /users/me/tag               -> 200 OK
4. POST /users/me/pin               -> 201 Created
5. GET  /identity/upload-signature  -> 200 OK      (signed payload)
6. [Upload selfie directly to Cloudinary]
7. POST /identity/verify            -> 200 OK      (VERIFIED | REJECTED | WATCHLISTED | NOT_FOUND)
8. Navigate to the home screen
```

> See [Section 9](#9-identity-verification-kyc) for the full identity verification flow.

> **UI guidance (Google sign-in):** At the profile step, always ask the user to enter or confirm their First, Middle, and Last name manually. Legal names must match their identity documents for KYC.

> **After onboarding:** the user has a profile, an `@tag`, a `PIN`, and (optionally) verified identity. The account balance starts at zero. To fund the account or send money, see [Section 7.3 (Transfers)](#73-transfers), [Section 7.4 (Accounts)](#74-accounts), [Section 7.5 (Transactions)](#75-transactions), and [Section 7.6 (Funding)](#76-funding).

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

### 7.3 Transfers

Two-step flow: quote, then confirm. All endpoints require `Authorization: Bearer <token>`.

#### Quote a transfer

```http
POST /transfers/quote
```

```json
{
  "recipient_tag": "david.ng",
  "amount_minor": 50000
}
```

* `recipient_tag` — full tag including country suffix. Leading `@` is stripped. Case-insensitive.
* `amount_minor` — integer, in the **sender's** currency, minor units. Minimum is `TRANSFER_MIN_AMOUNT_MINOR` (100). Does not include the fee.

Returns a full quote: sender currency, recipient summary (name, tag, currency), send amount, fee, total debit, receive amount, rate (as a decimal string, 6 decimal places), and an `expires_at` timestamp.

**Errors:** `RECIPIENT_NOT_FOUND`, `SELF_TRANSFER`, `VALIDATION_ERROR`, `CORRIDOR_UNSUPPORTED`, `RATE_UNAVAILABLE`, `FX_PROVIDER_UNAVAILABLE`.

#### Execute a transfer

```http
POST /transfers
```

```json
{
  "recipient_tag": "david.ng",
  "amount_minor": 50000,
  "idempotency_key": "01HZX8V5K2N3P4Q5R6S7T8U9V0",
  "pin": "48392"
}
```

Returns `201 Created` with the settled transaction: `transaction_id`, `status: "SETTLED"`, the applied `quote`, and `settled_at`. Both parties receive an email notification.

**Errors:** all from quote, plus `DUPLICATE_TRANSFER` (409, retry-safe — the original already settled), `PIN_INVALID`, `PIN_LOCKED`, `INSUFFICIENT_BALANCE`. A malformed idempotency key (wrong length or shape) surfaces as `VALIDATION_ERROR`, not a dedicated code — see the note under Section 5.

**Idempotency:** generate a unique `idempotency_key` per transfer attempt. On a network failure, retry with the **same key** — the backend will not settle twice. Do not generate a new key on retry.

#### Schedule a transfer

```http
POST /transfers/scheduled
```

```json
{
  "recipient_tag": "david.ng",
  "amount_minor": 50000,
  "idempotency_key": "01HZX8V5K2N3P4Q5R6S7T8U9V0",
  "pin": "48392",
  "execute_at": "2026-09-28T17:00:00Z"
}
```

* `execute_at` — UTC timestamp, must be in the future.
* The PIN is verified at scheduling time. It is **not** re-verified when the transfer fires.
* Returns `201 Created` with a scheduled-transfer record: `scheduled_transfer_id`, `status: "PENDING"`, `execute_at`.

The transfer fires automatically via the in-process scheduler, within a few seconds of `execute_at`. Transfers whose fire window has passed (5 minutes by default) are marked `FAILED` with reason `SCHEDULED_TRANSFER_EXPIRED` rather than fired late.

**This endpoint, and the list endpoint below, are fully functional today.** The two endpoints after that are not — read the warnings before building against them.

#### List scheduled transfers

```http
GET /transfers/scheduled
```

Returns all the caller's scheduled transfers, newest first. **Fully functional.**

#### Fetch a single scheduled transfer

```http
GET /transfers/scheduled/{scheduled_transfer_id}
```

> ⚠️ **Not yet functional.** This route is registered and reachable, but the service function it depends on (`scheduled_service.get_one`) is not implemented yet — calling it fails server-side rather than returning a clean 404 or the record. **Do not build a "view schedule details" screen against this until the backend confirms it's implemented.** In the meantime, the list endpoint above already returns every field this endpoint would — filter the list response client-side for the id you want instead.

Scoped, once implemented: a caller who is not the owner gets a 404.

#### Cancel a pending scheduled transfer

```http
POST /transfers/scheduled/{scheduled_transfer_id}/cancel
```

> ⚠️ **Not yet functional**, for the same reason as above — `scheduled_service.cancel` isn't implemented. **Do not ship a "cancel" button against this endpoint** until the backend confirms it works; a user who taps cancel and gets a raw server error is worse than not offering the feature yet.

Intended behavior, once implemented: only works on `PENDING` transfers. Returns `404 SCHEDULED_TRANSFER_NOT_FOUND` if the id is unknown or not owned by the caller. Returns `409` for anything already `SETTLED`, `FAILED`, or `CANCELLED` — the exact `error.code` for that specific conflict has not yet been confirmed against the backend source, so don't hardcode a guess for it.

**Statuses:** `PENDING`, `SETTLED`, `FAILED`, `CANCELLED`. Only `PENDING` is mutable.

### 7.4 Accounts

#### Get account balance

```http
GET /accounts/me
```

```json
{
  "success": true,
  "data": {
    "currency": "NGN",
    "balance_minor": 5713411,
    "balance_display": "57,134.11",
    "updated_at": "2026-09-25T18:47:03.115Z"
  },
  "error": null
}
```

* One account per user, in the user's country currency. Created automatically on first read.
* `balance_minor` is an integer in minor units. **Never a float.**
* `balance_display` is a pre-formatted string with thousands separators and the correct decimal places. Display it as-is; do not reformat.
* **XOF is special:** no minor unit, `balance_display` has zero decimals.

### 7.5 Transactions

#### List transaction history

```http
GET /transactions?limit=20
```

Returns the caller's transactions — both sent and received — newest first. Each item is described from the caller's perspective: `direction` is `"IN"` if the caller received money, `"OUT"` if the caller sent it. `counterparty` is the other party (never the caller). Null for funding (money came from outside) and withdrawal (money left outside).

* `limit` — optional query parameter, 1–100, default 20.
* `next_cursor` — opaque pagination cursor, or `null` if no more results. Do not parse it, pass it back verbatim.

#### Fetch a single transaction

```http
GET /transactions/{transaction_id}
```

Scoped: a caller who is neither the sender nor the recipient gets a 404, same as if the id didn't exist.

### 7.6 Funding

#### Get or create a virtual account

```http
POST /funding/virtual-account
```

No request body. Idempotent — returns the same account on repeat calls.

Response:

```json
{
  "success": true,
  "data": {
    "account_number": "1546629060",
    "bank_name": "NovaBanq GH",
    "account_name": "David Chashama Mensah",
    "currency": "GHS",
    "country": "GH",
    "provider_ref": "mock_cfc2fe49aed84907a6b9d1c91a256e58",
    "created_at": "2026-09-26T16:53:45.746965Z"
  },
  "error": null
}
```

The user gives this account number to their bank or mobile money app to make a deposit.

* `provider_ref` — the provider's opaque reference for this account. Save it; you need it to fire the demo webhook.

#### Receive deposit webhook

```http
POST /webhooks/flutterwave
```

**Not called by the mobile app in production.** Called by Flutterwave when a deposit settles. **For the demo**, the app fires this directly with a payload that mimics Flutterwave's, so the whole funding pipeline runs.

Request body:

```json
{
  "event": "charge.completed",
  "data": {
    "id": "demo-1790461559309",
    "tx_ref": "mock_cfc2fe49aed84907a6b9d1c91a256e58",
    "amount": 250.00,
    "currency": "GHS",
    "status": "successful"
  }
}
```

* `data.id` — must be **unique per deposit**. Use `"demo-${DateTime.now().millisecondsSinceEpoch}"`.
* `data.tx_ref` — the `provider_ref` from the virtual account response.

Response:

```json
{
  "success": true,
  "data": { "status": "ok", "credited": true },
  "error": null
}
```

`credited: true` means the ledger credited the user's balance. `credited: false` means the event was a duplicate, was ignored (wrong event type or status), or was rejected as corrupt.

### 7.7 AI Assistant

Three endpoints, all authenticated the same way as every other user-facing endpoint.

#### Parse a natural-language transfer instruction

```http
POST /ai/parse-transfer
```

```json
{ "text": "send 5000 to david.ng at 5pm" }
```

Returns the structured intent (amount, recipient, optional `execute_at`), the resolved recipient's full name, the full quote, and the original text. Read-only — no money moves. The frontend uses this to render a confirmation screen.

#### Execute a natural-language transfer

```http
POST /ai/execute-transfer
```

```json
{
  "text": "send 5000 to david.ng",
  "pin": "48392",
  "confirmed_recipient_uid": null
}
```

Returns `201 Created` with a **discriminated union**:

* `data.kind: "IMMEDIATE"` — the transfer settled. The full `TransferResponse` is in `data.transfer`.
* `data.kind: "SCHEDULED"` — a schedule was created. The full `ScheduledTransferResponse` is in `data.scheduled_transfer`.

* The PIN is never sent to the language model. It's a separate request field.
* `confirmed_recipient_uid` — optional. If provided, the tag is re-resolved and the request is rejected if it resolves to a different uid. This supports the two-step confirm flow.

#### Ask Nova a question

```http
POST /ai/ask
```

```json
{ "question": "who did I send money to last?" }
```

Returns Nova's answer. The `data.kind` field is the classification — one of `GREETING`, `BALANCE`, `LAST_RECIPIENT`, `SPENDING_SUMMARY`, `COUNTERPARTY_DETAILS`, `SPENDING_ADVICE`, `GENERAL_FINANCE`, `TRANSFER_INTENT`, `UNKNOWN`. The `data.answer` is Nova's natural-language reply. The `data.data` is the structured numbers behind the answer, or `null`.

Nova answers questions about balance, spending, counterparties, and general money topics. She cannot execute a transfer from this endpoint — a "send X to Y" instruction returns kind `TRANSFER_INTENT` with a redirect reply pointing at the send flow.

**Fail-soft:** unrecognized questions become `UNKNOWN` with a helpful fallback, never a 500. Only an unreachable Gemini or a Firestore failure on a data-backed kind returns an error.

**Error codes for all three AI endpoints reuse existing values** (`VALIDATION_ERROR` for unparseable input or a stale recipient confirmation, `INTERNAL_ERROR` for a down AI provider) rather than introducing dedicated ones — don't assume codes like `INTENT_UNPARSEABLE` exist without checking `app/core/constants.py` first. See `docs/ai_implementation.md` for the full breakdown.

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

## 9. Identity Verification (KYC)

Two endpoints support the BVN + selfie verification flow. The selfie is uploaded directly to Cloudinary by the mobile client — the backend never handles image bytes.

### 9.1 Step 1 — Get a signed upload payload

```http
GET /identity/upload-signature
Authorization: Bearer <token>
```

Response:

```json
{
  "success": true,
  "data": {
    "api_key": "123456789012345",
    "cloud_name": "novabanq",
    "folder": "kyc-temp",
    "timestamp": 1727116800,
    "access_mode": "authenticated",
    "signature": "a1b2c3d4e5f6..."
  },
  "error": null
}
```

The mobile client POSTs these values plus the image file to Cloudinary's upload endpoint. The signature authorizes the upload and pins the folder and access mode — the client cannot override them.

### 9.2 Step 2 — Send the Cloudinary `public_id` to the backend

```http
POST /identity/verify
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "bvn": "12345678901",
  "cloudinary_public_id": "kyc-temp/abc123def456"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "status": "VERIFIED",
    "confidence": 0.99,
    "bvn_masked": "*******8901",
    "verified_at": "2026-09-24T15:04:44.12Z"
  },
  "error": null
}
```

### 9.3 The `status` field

| Status | Meaning | Client behavior |
| --- | --- | --- |
| `VERIFIED` | Identity confirmed | Proceed to dashboard |
| `REJECTED` | Face did not match | Allow retry with a clearer selfie |
| `WATCHLISTED` | Record flagged | Hard reject — contact support |
| `NOT_FOUND` | BVN not in the database | Prompt the user to check the BVN |

### 9.4 Notes

* The selfie is deleted from Cloudinary automatically once the check completes, regardless of outcome. Do not attempt to reuse the `public_id`.
* Once a user is verified, calling `POST /identity/verify` again returns `409 IDENTITY_ALREADY_VERIFIED`.
* The full BVN is never returned to the client. Only the last 4 digits are visible, masked.
* The face image is never returned to the client.
* `GET /identity/upload-signature` doesn't reserve or validate anything — it just proves the upload was authorized. Calling it repeatedly is safe.

---

## 10. Testing and Integration

### 10.1 Swagger UI

Open https://novabanq-api.onrender.com/docs to test endpoints manually.

1. Generate a valid user token (via the client SDK, or the terminal command below).
2. Click **Authorize** (top right).
3. Paste the token and confirm.

### 10.2 Generate a test token from the terminal

```bash
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=YOUR_FIREBASE_WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@novabanq.dev","password":"test1234","returnSecureToken":true}'
```

Copy `idToken` from the response and use it as the Bearer token.

---

## 11. What Is Real vs Mocked

Current scope is a hackathon build.

| Feature | Status | Details |
| --- | --- | --- |
| Firebase Authentication | Production-ready | Fully integrated |
| Firestore database | Production-ready | Real persistence |
| Email OTP | Production-ready | Sent via Brevo |
| Phone verification | Production-ready | Firebase native SMS |
| BVN / face verification | Real | Via Prembly sandbox (configurable via `KYC_PROVIDER`) |
| National ID verification | Not implemented | — |
| KYC image hosting | Real | Selfies uploaded directly to Cloudinary by the client, deleted once verification completes |
| Account numbers | Placeholder | 10-digit NovaBanq-internal numbers. Not real bank accounts — will be replaced with real NUBANs once virtual accounts go live via Flutterwave. |
| Double-entry ledger | Production-ready | Atomic Firestore transactions, per-currency balancing, idempotency keys |
| Account balances | Production-ready | One account per user in their own currency |
| Transfers | Production-ready | Quote + execute, 5-leg cross-currency settlement, PIN verification, idempotency |
| Scheduled transfers | **Partially implemented** | Creating (`POST /transfers/scheduled`) and listing (`GET /transfers/scheduled`) are production-ready; the in-process scheduler (APScheduler) fires due transfers every 30 seconds and works correctly. **Fetch-one and cancel are routed but not backed by service logic yet — calling them fails server-side.** See Section 7.3. |
| Transaction history | Production-ready | `GET /transactions`, `GET /transactions/{id}` |
| Funding (virtual account) | **Mocked** | The `MockVirtualAccountProvider` generates account numbers deterministically. The real Flutterwave provider is a stub. |
| Funding webhook | **Mocked** | Fired by the demo app instead of Flutterwave. In production, the real provider signs the request with `verif-hash` and the backend verifies it. |
| Email notifications | Production-ready | Sent via Brevo: welcome, transfer sent/received, withdrawal confirmed, PIN lockout, funding received |
| AI assistant (Nova) | Production-ready | Nine classification kinds, two Gemini calls per question, fail-soft discipline |
| AI transfer parsing | Production-ready | Natural-language instructions become real transfers or schedules. Inherits the same fetch-one/cancel gap as plain scheduled transfers, since both go through the same underlying service. |
| Real money movement | None | The platform is a closed-loop ledger. Deposits and withdrawals are the only rails that touch real money, and both are mocked for the demo. |

---

## 12. Project Structure

```text
app/
├── main.py                  FastAPI app initialization + in-process scheduler
├── api/                     Route aggregation and versioning
├── core/                    Config, security handlers, exceptions, shared utils
├── infra/                   Third-party adapters (Firebase, Firestore, Brevo, Cloudinary, FxRatesAPI, virtual accounts)
└── features/                Domain-driven feature modules
    ├── users/               Profile, identity claims, transaction PIN
    ├── otp/                 Email verification delivery
    ├── tags/                Unique @tag handles
    ├── account_numbers/     Account number generation
    ├── identity/            BVN + selfie KYC via Prembly, Cloudinary upload signing
    ├── accounts/            Balances — one account per user
    ├── ledger/              Double-entry bookkeeping engine
    ├── currency/            FX rates and per-corridor fees
    ├── transfers/           Quote, execute, scheduled transfers, AI-assisted parsing
    ├── transactions/        History and receipts
    ├── funding/             Virtual accounts + deposit webhook
    ├── ai_intent/           Nova — the AI assistant and transfer parser
    └── notifications/       Transactional email orchestration
```

Each feature module has up to four layers:

| File | Responsibility |
| --- | --- |
| `router.py` | API routes (controllers) |
| `schemas.py` | Pydantic request/response models |
| `service.py` | Business logic |
| `repository.py` | Firestore access |

Some modules have additional files where the domain warrants it — `transfers/` includes `executor.py`, `fee_calculator.py`, `validator.py`, `idempotency.py`, and the `scheduled_*` trio. `ai_intent/` includes the `ask_*` group for the conversational assistant.

---

## 13. Local Backend Setup

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

## 14. Running Tests

```bash
pytest tests/ -v -s
```

`tests/test_auth.py` runs integration tests against a live local server connected to Firebase and Firestore. Set `FIREBASE_WEB_API_KEY` in your local `.env` first.

---

## 15. Support

* **API specs and contracts:** contact the primary backend engineer.
* **Authentication platform:** check the project's Firebase Console settings.
* **AI features (Nova, transfers, ask):** see `docs/ai_implementation.md` for the full technical reference.
* **Full endpoint contract:** see `docs/api-contract.md` for detailed request/response shapes and error tables.
* **Demo funding:** see `docs/demo-funding.md` for the deposit-simulation flow.