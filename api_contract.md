# NovaBanq — API Contract

**Audience:** The Flutter developer integrating with the NovaBanq backend.

**Purpose:** Reference for every endpoint the mobile client calls. This
document covers the request and response shape of each endpoint, the
error codes you'll see, and the flows that chain them together.

**Companion document:** `FRONTEND_AUTH_GUIDE.md` covers Firebase Auth —
signup, Google Sign-In, phone verification, and KYC. Read that first if
you haven't. This document assumes the user is authenticated and has a
valid Firebase ID token in hand.

**How to use this document:** Sections 1–3 are reference material you
set up once (base URL, the response envelope, how errors are shaped)
and rarely revisit after that. Sections 4–6 walk through each endpoint
the mobile client actually calls, in the order you'll build the screens
that use them. Section 7 is the one to keep open while you build the
send-money flow — it stitches sections 4–6 together into the real,
moment-by-moment sequence, including the two behaviors that are easiest
to get wrong (idempotency and quote expiry). Sections 8–9 are lookup
tables you'll come back to repeatedly rather than read start to finish:
how to format money correctly, and what every error code means.

---

## ⚠️ Not Yet Confirmed — Read Before Building Against These

Everything else in this document comes straight from the backend code.
These five specifics are best-effort and need a quick confirmation from
the backend engineer before the frontend hard-codes anything around
them:

1. **`POST /users/me/pin/reset` error codes** (Section 9, *Auth-related*) —
   `PIN_ALREADY_SET` and `PIN_INVALID` are confirmed for
   `POST /users/me/pin` and `POST /users/me/pin/verify` respectively.
   The **reset** endpoint's own error codes haven't been checked
   against its actual implementation — treat them as a placeholder.
2. **`balance_display`'s exact format** (Section 4, Section 8) — shown here as a
   plain decimal string (`"57134.11"`): no thousands separator, no
   currency symbol. If the real response includes either, both the
   example in Section 4 and the "prefer `balance_display`" guidance in Section 8
   need a small update.
3. **`transaction_id` vs. `idempotency_key` formats** (Section 6) — the
   examples use a UUIDv4 for `transaction_id` (confirmed — the ledger
   generates it as `str(uuid.uuid4())`) and a ULID for
   `idempotency_key` (taken from the request schema's example string,
   not independently confirmed). These are deliberately different
   fields for different purposes, but double-check whether the client
   is free to generate the key in *either* format or whether one is
   specifically required.
4. **`XOF`'s display symbol** (Section 8) — shown as `CFA`. If the product
   wants `F CFA`, `₣`, or something else instead, it's a one-line fix
   — but it should be a single fixed mapping the whole app uses.
5. **`RATE_UNAVAILABLE` vs. `FX_PROVIDER_UNAVAILABLE`** (Section 5, Section 6, Section 9) —
   both currently map to 502 and are documented here as
   interchangeable for UX purposes ("show a generic try-again message
   for either"). If the product wants them to feel different to the
   user — e.g. one is worth an automatic retry sooner than the other —
   they should be split apart in this doc first.

---

## Table of Contents

1. [Base URL and Authentication](#1-base-url-and-authentication)
2. [Response Envelope](#2-response-envelope)
3. [Error Handling](#3-error-handling)
4. [Accounts — Reading Balances](#4-accounts--reading-balances)
5. [Transfers — Quote](#5-transfers--quote)
6. [Transfers — Execute](#6-transfers--execute)
7. [The Complete Transfer Flow](#7-the-complete-transfer-flow)
8. [Formatting Amounts for Display](#8-formatting-amounts-for-display)
9. [Error Code Reference](#9-error-code-reference)

---

## 1. Base URL and Authentication

**Base URL:**

```
https://novabanq-api.onrender.com/api/v1
```

**Interactive docs (Swagger UI):**

```
https://novabanq-api.onrender.com/docs
```

Every endpoint except `/health` requires a Firebase ID token:

```
Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

Get the token with `FirebaseAuth.instance.currentUser?.getIdToken()`.
See the auth guide for token handling and the refresh-on-401 pattern.

---

## 2. Response Envelope

**Every** response — success or error — uses the same outer shape:

**Success:**

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

**Error:**

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RECIPIENT_NOT_FOUND",
    "message": "No user found with that tag.",
    "details": {}
  }
}
```

**Rules:**

- **Switch on `error.code`, never on `error.message`.** The code is
  stable and machine-readable; the message is for logs and debugging,
  and its exact wording can change without notice.
- **Every endpoint returns the same envelope.** Even `/health`, even
  422 validation errors, even 500s. Your HTTP client can unwrap once,
  in one place, rather than special-casing individual endpoints.
- **`details` is `{}` by default**, but validation errors populate it —
  see [Error Handling](#3-error-handling).

---

## 3. Error Handling

### The shape of an error

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance for this transaction.",
    "details": {}
  }
}
```

### HTTP status codes

| Status | Meaning | What to do |
|---|---|---|
| 200 | Success | Read `data` |
| 201 | Created | Read `data` (used by POST endpoints that create a resource) |
| 401 | Token missing, malformed, or expired | Call `getIdToken(true)` and retry once; if it fails again, re-login |
| 403 | Token valid, but user lacks permission (e.g. email not verified) | Route the user to the required step |
| 404 | Resource not found | Show the specific not-found message from `error.code` |
| 409 | Conflict (duplicate, already-exists) | Usually means the operation already happened; fetch the original |
| 422 | Business rule violated, or validation failed | Show field errors or a specific message |
| 429 | Rate-limited or locked (e.g. PIN lockout) | Show a wait message; back off |
| 500 | Server error | Log the request id if present; retry once |
| 502 | Upstream provider failed (FX, KYC, email) | Show "try again later" |

### Validation errors (422)

When Pydantic rejects the request body, `details.fields` names the
offending fields:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": {
      "fields": {
        "amount_minor": "Input should be greater than or equal to 100",
        "recipient_tag": "Tag must be in the form 'name.country'."
      }
    }
  }
}
```

Map `details.fields` to inline errors on the corresponding form inputs.

---

## 4. Accounts — Reading Balances

Each user has exactly one account, in their own country's currency. The
account is created automatically on first read — you never call a
"create account" endpoint, and there is no "account not found" case to
handle.

### `GET /accounts/me`

**Request:**

```
GET /api/v1/accounts/me
Authorization: Bearer <token>
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "currency": "NGN",
    "balance_minor": 5713411,
    "balance_display": "57134.11",
    "updated_at": "2026-09-25T18:47:03.115Z"
  },
  "error": null
}
```

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `currency` | string | One of `NGN`, `GHS`, `KES`, `XOF`, `ZAR`. Fixed at account creation; never changes. |
| `balance_minor` | integer | Balance in **minor units** of the currency. Never a float. See [Formatting Amounts](#8-formatting-amounts-for-display). |
| `balance_display` | string | Same amount as a decimal string with the currency's standard decimal places. **Display this directly** — do not reformat `balance_minor` yourself unless you need a different style. Exact format not yet confirmed — see the callout above. |
| `updated_at` | ISO 8601 timestamp | When the balance last changed. |

**Pagination:** none — a user has one account.

**Caching:** the balance changes when the user sends or receives money.
Poll it after a successful transfer, or after a push notification fires.

---

## 5. Transfers — Quote

A quote is a **read-only price estimate**. No money moves. You can call
it as often as you like — every call recomputes against the current FX
rate.

**When to call it:** when the user reaches the confirm screen, after
they've entered an amount and chosen a recipient. Display the quote to
the user; they confirm or cancel.

### `POST /transfers/quote`

**Request:**

```
POST /api/v1/transfers/quote
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "recipient_tag": "chidera.ng",
  "amount_minor": 50000
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `recipient_tag` | string | yes | The recipient's full `@tag`, including country suffix. A leading `@` is accepted and stripped. Case-insensitive. |
| `amount_minor` | integer | yes | Amount the sender is sending, in **their own currency's minor units**. Must be ≥ `100` (the platform minimum). Does **not** include the fee. |

**Do not send the sender's currency.** It's read from the sender's
profile. A client cannot state its own currency.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "sender_currency": "GHS",
    "recipient": {
      "uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2",
      "tag": "chidera.ng",
      "display_name": "Temi Adeyemi",
      "country": "NG",
      "currency": "NGN"
    },
    "send_amount_minor": 50000,
    "fee_minor": 500,
    "total_debit_minor": 50500,
    "receive_amount_minor": 5713411,
    "rate": "114.268226",
    "expires_at": "2026-09-26T10:03:25.182Z"
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `sender_currency` | string | The currency the sender pays in. |
| `recipient` | object | Public identity of the recipient. No balance, no KYC flags. |
| `send_amount_minor` | integer | Echo of what the sender entered. |
| `fee_minor` | integer | NovaBanq's fee, in sender-currency minor units. 1% of `send_amount_minor`, rounded up. |
| `total_debit_minor` | integer | `send_amount_minor + fee_minor`. **This is what leaves the sender's balance.** |
| `receive_amount_minor` | integer | What the recipient receives, in **recipient-currency** minor units. |
| `rate` | string | Exchange rate as a decimal string, 6 decimal places. `1 sender_currency = {rate} recipient_currency`. |
| `expires_at` | ISO 8601 timestamp | After this time, re-quote before confirming. The server does not enforce this on execute — the execute recomputes from scratch — but the user's confirmation should be against a fresh quote. |

**Rendering the quote:**

> "You're sending **GHS 505.00** (500.00 + 5.00 fee), which is
> **₦57,134.11**, to **Temi Adeyemi** (@chidera.ng)."

**Errors:**

| Status | Code | Meaning |
|---|---|---|
| 404 | `RECIPIENT_NOT_FOUND` | The tag resolves to no user. |
| 422 | `SELF_TRANSFER` | Sender and recipient are the same user. |
| 422 | `VALIDATION_ERROR` | Bad request body. See `details.fields`. |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor for the currency pair. |
| 502 | `RATE_UNAVAILABLE` | FX provider down and cache too stale. |
| 502 | `FX_PROVIDER_UNAVAILABLE` | FX provider rejected the request. |

---

## 6. Transfers — Execute

Execute settles the transfer through the ledger. **This is the endpoint
that moves money.** It should only be called after the user confirms
the quote on the confirm screen.

### `POST /transfers`

**Request:**

```
POST /api/v1/transfers
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "recipient_tag": "chidera.ng",
  "amount_minor": 50000,
  "idempotency_key": "01HZX8V5K2N3P4Q5R6S7T8U9V0",
  "pin": "48392"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `recipient_tag` | string | yes | Same as the quote. |
| `amount_minor` | integer | yes | Same as the quote. |
| `idempotency_key` | string | yes | Client-generated unique key, 8–128 characters. **See below.** |
| `pin` | string | yes | The user's 5-digit transaction PIN. Exactly 5 digits. |

### The idempotency key — read this carefully

The idempotency key is the single most important field on this request.
Its job is to make the transfer **safe to retry**.

**Rules:**

1. **Generate it once, per transfer attempt, before the first request.**
   A UUIDv4 or ULID works. Do not derive it from the amount, the
   recipient, or the timestamp — you need uniqueness across attempts.

2. **If the first request fails for a *retryable* reason** (network
   timeout, 500, 502), retry with the **same key**. The backend sees
   the same key, does not settle a second time, and returns the
   original result. This is the whole point.

3. **If the first request fails for a *terminal* reason** (422
   `INSUFFICIENT_BALANCE`, 422 `PIN_INVALID`, 404
   `RECIPIENT_NOT_FOUND`), **generate a new key** on the next attempt.
   The first attempt didn't settle anything; the key is still unused
   but reusing it is confusing in logs.

4. **Never reuse a key for a different transfer.** Same key = same
   logical attempt, always.

5. **Persist the key** locally until the transfer reaches a terminal
   state (settled or rejected for a terminal reason). If the app is
   killed mid-request and relaunched, you need to retry with the same
   key, not a new one.

**Response (201):**

```json
{
  "success": true,
  "data": {
    "transaction_id": "1b9a1064-43f9-4581-b092-72261fe3c0ee",
    "status": "SETTLED",
    "quote": {
      "sender_currency": "GHS",
      "recipient": {
        "uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2",
        "tag": "chidera.ng",
        "display_name": "Temi Adeyemi",
        "country": "NG",
        "currency": "NGN"
      },
      "send_amount_minor": 50000,
      "fee_minor": 500,
      "total_debit_minor": 50500,
      "receive_amount_minor": 5713411,
      "rate": "114.268226",
      "expires_at": "2026-09-26T10:03:57.501Z"
    },
    "settled_at": "2026-09-26T10:03:12.501Z"
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `transaction_id` | string | The ledger's transaction identifier (a UUIDv4). Use it to fetch the receipt later. Note this is a different ID format from `idempotency_key` — see the callout above. |
| `status` | string | Always `"SETTLED"`. There is no other value on a success response. |
| `quote` | object | **The quote that was actually applied.** Re-read this on the receipt — it may differ from an earlier quote if the rate moved. Its own `expires_at` reflects when *this* recomputed quote expires, not when the transfer settled. |
| `settled_at` | ISO 8601 timestamp | When the ledger committed. |

**Errors:**

| Status | Code | Meaning | Retry with same key? |
|---|---|---|---|
| 404 | `RECIPIENT_NOT_FOUND` | Tag resolves to no user. | No — new key |
| 409 | `DUPLICATE_TRANSFER` | Same idempotency key, already settled. | **Yes** — the original succeeded; fetch it by key if you have the result |
| 422 | `PIN_INVALID` | Wrong PIN. Counts against the lockout. | No — new key |
| 422 | `SELF_TRANSFER` | Sender is the recipient. | No |
| 422 | `INSUFFICIENT_BALANCE` | Balance can't cover `total_debit_minor`. | No |
| 422 | `AMOUNT_INVALID` | Amount below minimum or malformed. | No |
| 422 | `VALIDATION_ERROR` | Body validation failed. | No |
| 429 | `PIN_LOCKED` | Too many wrong PINs. Wait 20 minutes. | No |
| 500 | `INTERNAL_ERROR` | Server error. | **Yes** — same key |
| 502 | `INTERNAL_ERROR` (ledger) | Ledger unavailable. | **Yes** — same key |
| 502 | `RATE_UNAVAILABLE` | FX provider down. | **Yes** — same key |

**Retry semantics:** the only safe retries are 500, 502, and network
timeouts. Retrying a 409 will return 409 again — that's not a failure,
it's a confirmation that the first attempt succeeded. Retrying a 4xx
will fail the same way unless you fix the request first.

### PIN and lockout

- The PIN is verified against a bcrypt hash, same as
  `POST /users/me/pin/verify`.
- **Five consecutive wrong attempts lock PIN entry for 20 minutes.**
  The count resets on a successful attempt.
- A locked PIN returns 429 `PIN_LOCKED`, and **the attempt is not
  counted** — the lockout period is fixed at 20 minutes from the
  triggering failure.
- While locked, **even the correct PIN** returns 429. There is no
  bypass.

---

## 7. The Complete Transfer Flow

```
 1. User opens the "Send" screen
 2. User enters recipient tag (@chidera.ng) and amount (GHS 500.00)
 3. → POST /transfers/quote    { recipient_tag, amount_minor }
 4. → Display: "You're sending GHS 505.00, which is ₦57,134.11, to Temi."
 5. User taps "Confirm"
 6. → Show PIN entry screen
 7. User enters PIN
 8. → Generate a new idempotency_key (UUIDv4)
 9. → POST /transfers           { recipient_tag, amount_minor,
                                   idempotency_key, pin }
10. → On 201: show the receipt using the embedded `quote` object,
     update the balance via GET /accounts/me, and navigate to history
11. → On 4xx terminal error: show the specific message from error.code
12. → On 5xx or timeout: retry the request (up to ~3 times) with the
     SAME idempotency_key
```

### Handling `expires_at`

The quote response has an `expires_at` timestamp. If the user sits on
the confirm screen past that time:

- **Disable the confirm button** and show a "Refresh quote" action.
- **Do not** proceed to execute with a stale quote. The execute
  recomputes from scratch anyway, so the amounts on the receipt might
  not match what the user confirmed.

The typical lock window is 45 seconds. That's enough for a PIN entry
but not for a user to walk away and come back.

### Handling 409 `DUPLICATE_TRANSFER`

This is not a failure. It means the transfer with this idempotency key
**already succeeded** on a previous request, and the backend is
confirming that by refusing to settle a second time.

**What to do:**

- If your retry logic caught this, it means the original response was
  lost in transit. **Fetch the transaction** (via `GET /transfers/{id}`
  — currently unimplemented, coming soon) to reconstruct the receipt.
- **Do not** generate a new key and retry. That would settle a second
  transfer for the same money.

Until the receipt endpoint exists, cache the `transaction_id` from a
successful response and use it to look up the transfer after a
duplicate-detection event.

---

## 8. Formatting Amounts for Display

**All amounts in every API request and response are integers in the
currency's minor units.** Never floats, never strings-as-numbers.

| Currency | Minor unit | Multiplier | Example |
|---|---|---|---|
| NGN | kobo | 100 | `5713411` minor = ₦57,134.11 |
| GHS | pesewas | 100 | `50500` minor = GHS 505.00 |
| KES | cents | 100 | `5000` minor = KES 50.00 |
| ZAR | cents | 100 | `5000` minor = R 50.00 |
| **XOF** | **none** | **1** | `57134` minor = CFA 57,134 |

**XOF is special.** It has no minor unit. `balance_minor` for an XOF
account is already in whole francs. Do not divide by 100.

**Do not do arithmetic on floats.** If you need to compute a display
string from `balance_minor` (rare — the API already returns
`balance_display`), use integer division and modulus, or Dart's
`Decimal` package. `balance_minor / 100.0` will produce
`57134.10999999999` on some platforms.

**Prefer `balance_display` from the API.** It's a pre-formatted string
with the correct number of decimal places for the currency. Only
reformat if you need a different style (thousands separators, symbol
placement). Its exact format isn't independently confirmed yet — see
the callout above.

**Currency symbols for display:**

| Currency | Symbol |
|---|---|
| NGN | ₦ |
| GHS | GH₵ |
| KES | KSh |
| XOF | CFA *(placeholder — confirm final symbol, see callout above)* |
| ZAR | R |

---

## 9. Error Code Reference

Every code the transfers and accounts endpoints can return. Switch on
these strings — never on HTTP status alone, and never on the message.

### Transfers

Covers both `POST /transfers/quote` and `POST /transfers` — not every
endpoint returns every code below; see Section 5 and Section 6 for which codes apply
to which one.

| Code | HTTP | Meaning | Suggested UX |
|---|---|---|---|
| `RECIPIENT_NOT_FOUND` | 404 | Tag resolves to no user | "No one found with that @tag. Check the spelling." |
| `SELF_TRANSFER` | 422 | Sender is the recipient | "You can't send money to yourself." |
| `AMOUNT_INVALID` | 422 | Amount below minimum or malformed | "Minimum transfer is 1.00." |
| `CORRIDOR_UNSUPPORTED` | 422 | No FX corridor for the pair | "Transfers to this currency aren't supported yet." |
| `INSUFFICIENT_BALANCE` | 422 | Balance can't cover total debit | "You need X more to send this." |
| `PIN_INVALID` | 422 | Wrong PIN (counts toward lockout) | "Incorrect PIN. N attempts remaining." |
| `PIN_LOCKED` | 429 | Too many wrong attempts | "PIN locked. Try again in 20 minutes." |
| `DUPLICATE_TRANSFER` | 409 | Key already used, original settled | Show the original receipt (see Section 7) |
| `RATE_UNAVAILABLE` | 502 | FX provider down, cache too stale | "Rate unavailable. Try again in a moment." |
| `FX_PROVIDER_UNAVAILABLE` | 502 | FX provider rejected the request | Same as above — see the callout above if these should ever differ |
| `VALIDATION_ERROR` | 422 | Request body invalid | Show `details.fields` inline |
| `INTERNAL_ERROR` | 500/502 | Server or ledger error | Retry with the same idempotency key |

### Accounts

| Code | HTTP | Meaning |
|---|---|---|
| `USER_NOT_FOUND` | 404 | Profile missing — user hasn't completed onboarding |
| `ACCOUNT_NOT_FOUND` | 404 | Reserved; not returned in practice (account auto-creates) |

### Auth-related (see the auth guide)

| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_REQUIRED` | 401 | No Authorization header |
| `AUTH_INVALID` | 401 | Token malformed, expired, or revoked |
| `EMAIL_NOT_VERIFIED` | 403 | User hasn't completed email OTP |
| `USER_ALREADY_EXISTS` | 409 | Profile already created for this uid |
| `TAG_TAKEN` | 409 | The requested @tag is claimed |
| `PIN_ALREADY_SET` | 409 | PIN already set; use reset flow |
| `PIN_INVALID` | 422 | Wrong PIN (see transfers) |
| `PIN_LOCKED` | 429 | Locked (see transfers) |

`PIN_ALREADY_SET` and `PIN_INVALID` above are confirmed for
`POST /users/me/pin` and `POST /users/me/pin/verify`. The codes
`POST /users/me/pin/reset` itself returns haven't been checked — see
the callout above.

---

## Appendix — Full Endpoint Index

For reference, every endpoint currently deployed. Endpoints marked
**(planned)** are not yet available.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/users/me` | Read profile |
| POST | `/api/v1/users/me` | Create profile |
| PATCH | `/api/v1/users/me/names` | Update name fields |
| GET | `/api/v1/users/me/tag/check` | Check tag availability |
| POST | `/api/v1/users/me/tag` | Claim a @tag |
| POST | `/api/v1/users/me/phone/verify` | Mark phone verified |
| POST | `/api/v1/users/me/pin` | Set PIN |
| POST | `/api/v1/users/me/pin/verify` | Verify PIN |
| POST | `/api/v1/users/me/pin/reset` | Reset PIN |
| POST | `/api/v1/otp/email/send` | Send email OTP |
| POST | `/api/v1/otp/email/verify` | Verify email OTP |
| GET | `/api/v1/identity/upload-signature` | Get Cloudinary signature |
| POST | `/api/v1/identity/verify` | Verify BVN + selfie |
| GET | `/api/v1/accounts/me` | Read account balance |
| POST | `/api/v1/transfers/quote` | Price a transfer |
| POST | `/api/v1/transfers` | Execute a transfer |
| GET | `/api/v1/transfers/{transaction_id}` | Fetch a receipt **(planned)** |
| GET | `/api/v1/transactions` | List transaction history **(planned)** |
| POST | `/api/v1/funding/virtual-account` | Create virtual account for deposit **(planned)** |
| POST | `/api/v1/withdrawals` | Withdraw to bank/mobile money **(planned)** |

That's 17 live endpoints and 4 planned ones.

---

**Questions?** Ping the backend engineer with:

1. The exact request (method, URL, headers, body)
2. The exact response (status, body)
3. The `error.code` value
4. The approximate timestamp

That's everything needed to trace the request through the logs.