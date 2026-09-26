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
and rarely revisit after that. Sections 4–7 walk through each endpoint
the mobile client actually calls, in the order you'll build the screens
that use them. Section 8 is the one to keep open while you build the
send-money flow — it stitches sections 5–7 together into the real,
moment-by-moment sequence, including the two behaviors that are easiest
to get wrong (idempotency and quote expiry). Sections 9–10 are lookup
tables you'll come back to repeatedly rather than read start to finish:
how to format money correctly, and what every error code means.

---

## ⚠️ Not Yet Confirmed — Read Before Building Against This

Everything else in this document has been confirmed against the
backend code. One thing is still genuinely open:

**`XOF`'s display symbol** (Section 9) — shown here as `CFA`. This is
a product decision, not a technical one: confirm with the design lead
whether `CFA`, `F CFA`, `₣`, or something else is correct before
shipping it. Whichever symbol you land on, put it behind a single
`symbolFor(Currency)` function (see Section 9) rather than hardcoding
it at each call site, so changing it later is a one-line fix instead
of a find-and-replace across the app.

---

## Table of Contents

1. [Base URL and Authentication](#1-base-url-and-authentication)
2. [Response Envelope](#2-response-envelope)
3. [Error Handling](#3-error-handling)
4. [Accounts — Reading Balances](#4-accounts--reading-balances)
5. [Transfers — Quote](#5-transfers--quote)
6. [Funding — Depositing Money](#6-funding--depositing-money)
7. [Transfers — Execute](#7-transfers--execute)
8. [The Complete Transfer Flow](#8-the-complete-transfer-flow)
9. [Formatting Amounts for Display](#9-formatting-amounts-for-display)
10. [Error Code Reference](#10-error-code-reference)

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
| 502 | Upstream provider failed (FX, KYC, email, funding) | Show "try again later" |

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
| `balance_minor` | integer | Balance in **minor units** of the currency. Never a float. See [Formatting Amounts](#9-formatting-amounts-for-display). |
| `balance_display` | string | Same amount as a decimal string with the currency's standard decimal places. **Display this directly** — do not reformat `balance_minor` yourself unless you need a different style. Format is a plain decimal string: no thousands separator, no currency symbol, no leading/trailing whitespace. For NGN, GHS, KES, and ZAR it has two decimal places; for XOF it has zero. If you want a currency symbol or thousands separators, add them at the widget layer — don't re-derive the number. |
| `updated_at` | ISO 8601 timestamp | When the balance last changed. |

**Pagination:** none — a user has one account.

**Caching:** the balance changes when the user sends money, receives
money, or funds their account. Poll it after a successful transfer,
after a funding webhook fires, or after a push notification.

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
| 404 | `USER_NOT_FOUND` | Profile missing — shouldn't happen for an authenticated request, but documented for completeness. |
| 404 | `RECIPIENT_NOT_FOUND` | The tag resolves to no user. |
| 422 | `SELF_TRANSFER` | Sender and recipient are the same user. |
| 422 | `VALIDATION_ERROR` | Bad request body. See `details.fields`. |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor for the currency pair. |
| 502 | `RATE_UNAVAILABLE` | Provider unreachable AND cache older than 1 hour. Transient — retry may succeed. |
| 502 | `FX_PROVIDER_UNAVAILABLE` | Provider responded with an error (auth, quota, bad request). Retry will fail until fixed. |

---

## 6. Funding — Depositing Money

Funding is how a user gets money **into** their NovaBanq account. In
production, the user transfers money from their bank or mobile money
app to a NovaBanq-issued virtual account number; the bank routes the
payment through Flutterwave, Flutterwave sends a webhook to NovaBanq,
and the ledger credits the user's balance automatically.

**For the hackathon demo, the webhook is fired directly by a button in
the app** instead of by Flutterwave — see "How the demo works" below.
Everything else — the virtual account, the ledger credit, the balance
update — is real.

### The flow, from the user's perspective

1. User taps "Add money" in the app.
2. App calls `POST /funding/virtual-account` and receives the user's
   account number, bank name, and currency.
3. App displays the account number and bank name on screen.
4. **In production:** user opens their bank app, enters the number,
   and sends money. Bank → Flutterwave → webhook → ledger credits.
   **In the demo:** the app fires `POST /webhooks/flutterwave` directly
   with a payload that mimics Flutterwave's.
5. App polls `GET /accounts/me` and shows the updated balance.

### `POST /funding/virtual-account`

Returns the user's virtual account. **Idempotent**: calling more than
once for the same user returns the same account, never a second one.
You call this every time the user opens the "Add money" screen; the
backend reuses the existing account.

**Request:**

```
POST /api/v1/funding/virtual-account
Authorization: Bearer <token>
```

No request body.

**Response (200):**

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

| Field | Type | Notes |
|---|---|---|
| `account_number` | string | The account number the user enters in their bank app. |
| `bank_name` | string | The bank shown alongside the account number. |
| `account_name` | string | Name on the account — the user's display name. |
| `currency` | string | The currency the account accepts. Matches the user's own currency. |
| `country` | string | The country the account is issued in. |
| `provider_ref` | string | The provider's opaque reference for this account. **Save this** — you'll need it to fire the demo webhook. It's stable for a given user, so one call per app session is enough. |
| `created_at` | ISO 8601 timestamp | When the virtual account was first created. |

**Errors:**

| Status | Code | Meaning |
|---|---|---|
| 401 | `AUTH_INVALID` | Token missing, expired, or malformed. |
| 404 | `USER_NOT_FOUND` | User hasn't completed onboarding. |
| 502 | `FUNDING_PROVIDER_UNAVAILABLE` | The virtual account provider can't issue an account. Raised by the real Flutterwave provider until it's implemented; not reachable while the mock provider is active. |
| 502 | `INTERNAL_ERROR` | Firestore or ledger failure. |

### `POST /webhooks/flutterwave`

Receives a deposit notification. **This endpoint is not called by the
mobile app in production** — it's called by Flutterwave. In the demo,
the app calls it directly to simulate a deposit.

**Request:**

```
POST /api/v1/webhooks/flutterwave
Content-Type: application/json
```

**No `Authorization` header.** The endpoint is authenticated by the
`verif-hash` header that Flutterwave sends, not by a Firebase token.

**Request body:**

```json
{
  "event": "charge.completed",
  "data": {
    "id": "test-event-001",
    "tx_ref": "mock_cfc2fe49aed84907a6b9d1c91a256e58",
    "amount": 250.00,
    "currency": "GHS",
    "status": "successful"
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `event` | string | yes | Only `"charge.completed"` is acted on. Any other value returns 200 with `credited: false`. |
| `data.id` | string or number | yes | A unique identifier for this deposit event. **Must be unique per deposit** — the backend uses it as the idempotency key. If you fire two deposits with the same `id`, the second is a no-op. For the demo, generate a fresh value per tap: `"demo-${DateTime.now().millisecondsSinceEpoch}"`. |
| `data.tx_ref` | string | yes | The `provider_ref` from the virtual account response. **Must match the user's current provider_ref** — a stale or unknown ref is rejected. |
| `data.amount` | number | yes | Amount in major units (e.g. `250.00` for GHS 250). Sent as a JSON number; the backend parses it as an exact Decimal. |
| `data.currency` | string | yes | Must match the virtual account's currency. A mismatch is rejected. |
| `data.status` | string | yes | Only `"successful"` credits the ledger. Any other value returns 200 with `credited: false`. |
| `data.customer` | object | no | Ignored by the backend; included for realism if you want. |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "credited": true
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | string | Always `"ok"`. |
| `credited` | boolean | `true` if the ledger was credited by this call. `false` if the event was a duplicate, was ignored (wrong event type or status), or was rejected as corrupt. **For the demo, this is the field to check** — if it's `true`, the balance went up. |

**Errors:**

| Status | Code | Meaning |
|---|---|---|
| 401 | `AUTH_INVALID` | `verif-hash` header missing or wrong. Only enforced when the real Flutterwave provider is active; skipped for the mock. |
| 422 | `VALIDATION_ERROR` | Body doesn't match the expected shape. |

**Note on HTTP status:** the webhook returns **200 for every well-formed
event**, whether the deposit was credited, was a duplicate, or was
rejected for a data-integrity reason (unknown ref, stale ref, currency
mismatch). Only a signature failure returns 401. This is deliberate —
Flutterwave retries non-2xx responses, and a corrupt payload will never
become valid on retry. Rejected-but-well-formed events are logged at
`CRITICAL` on the backend for monitoring.

### How the demo works

The demo app fires `POST /webhooks/flutterwave` directly. Here is the
complete Dart flow for a "Simulate deposit" button:

```dart
Future<void> simulateDeposit({
  required String providerRef,
  required String currency,
  required double amount,
}) async {
  // 1. Fire the webhook with a unique event id
  final response = await ApiClient.post('/webhooks/flutterwave', {
    'event': 'charge.completed',
    'data': {
      'id': 'demo-${DateTime.now().millisecondsSinceEpoch}',
      'tx_ref': providerRef,
      'amount': amount,
      'currency': currency,
      'status': 'successful',
    },
  });

  // 2. Check whether the ledger actually credited
  final credited = response['data']['credited'] as bool;
  if (!credited) {
    throw Exception('Deposit did not credit. Check the backend log.');
  }

  // 3. Refresh the balance
  await _refreshBalance();  // calls GET /accounts/me
}
```

**What to say to judges:**

> "The user gets a virtual account number here. In production they'd
> open their bank app, enter this number, and send money. The bank
> routes it through Flutterwave, Flutterwave sends us a webhook, and
> we credit the ledger. For the demo, this button fires the webhook
> directly — so you can see the whole pipeline work end to end."

**What not to claim:** that real money moved. Nothing in the demo
touches a real bank. The virtual account number is generated by
NovaBanq's own mock provider, not by Flutterwave. The Flutterwave
account is created and the integration is stubbed, but the API calls
are not wired in yet.

---

## 7. Transfers — Execute

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

**Format:** the field is a plain string, 8–128 characters. The
backend does not validate the format beyond that — it treats the key
as an opaque token and uses it verbatim as a Firestore document id.
UUIDv4 and ULID both work and are both good choices; ULID has the
advantage of being sortable, which is occasionally useful when
debugging logs. **Do not invent a custom format** (e.g. embedding the
amount or recipient in the key) — a key derived from the request is
the same key for two logically-different attempts, which defeats the
purpose. The example in this doc uses a ULID because it's the
schema's documented example; a UUIDv4 is equally valid.

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
| `transaction_id` | string | The ledger's transaction identifier (a UUIDv4), generated server-side. Use it to fetch the receipt later. This is intentionally a different ID than `idempotency_key` — you generate the key, the server generates the transaction id. |
| `status` | string | Always `"SETTLED"`. There is no other value on a success response. |
| `quote` | object | **The quote that was actually applied.** Re-read this on the receipt — it may differ from an earlier quote if the rate moved. Its own `expires_at` reflects when *this* recomputed quote expires, not when the transfer settled. |
| `settled_at` | ISO 8601 timestamp | When the ledger committed. |

**Errors:**

| Status | Code | Meaning | Retry with same key? |
|---|---|---|---|
| 404 | `USER_NOT_FOUND` | Sender's profile is missing. Shouldn't happen for an authenticated request. | No |
| 404 | `RECIPIENT_NOT_FOUND` | Tag resolves to no user. | No — new key |
| 409 | `DUPLICATE_TRANSFER` | Same idempotency key, already settled. | **Yes** — the original succeeded; fetch it by key if you have the result |
| 422 | `PIN_INVALID` | Wrong PIN. Counts against the lockout. | No — new key |
| 422 | `SELF_TRANSFER` | Sender is the recipient. | No |
| 422 | `INSUFFICIENT_BALANCE` | Balance can't cover `total_debit_minor`. | No |
| 422 | `AMOUNT_INVALID` | Amount below minimum or malformed. | No |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor for the currency pair. Execute re-runs the same validation as quote, so this is reachable here too. | No |
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

## 8. The Complete Transfer Flow

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

## 9. Formatting Amounts for Display

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

**Prefer `balance_display` from the API.** It's a pre-formatted
decimal string with the correct number of decimal places for the
currency — no thousands separators, no currency symbol. If you want
either, add them at the widget layer on top of `balance_display`:

```dart
final display = '₦${account.balanceDisplay}';     // ₦57134.11
final grouped = addThousandsSeparators(display);  // ₦57,134.11
```

Do not re-derive the number from `balance_minor` unless you have a
specific reason to. The API's string is authoritative, and re-deriving
risks float rounding on platforms where `double` can't represent the
value exactly.

**Currency symbols for display:** these are product decisions and may
differ from what's shown here. Confirm with the design lead before
hardcoding them in the app. The API does not return a symbol — only
the three-letter ISO code in `currency` — so symbol mapping is
entirely the client's responsibility.

| Currency | Suggested symbol | Notes |
|---|---|---|
| NGN | ₦ | |
| GHS | GH₵ | |
| KES | KSh | |
| XOF | CFA | West African CFA franc. If the product uses a different convention (F CFA, ₣), use that instead — and use it consistently across every screen. |
| ZAR | R | |

**Recommendation:** put this mapping in one Dart file
(`currency_symbols.dart`) with a single `symbolFor(Currency)` function,
and never hardcode a symbol at a call site. When the product changes
their mind about XOF, you change one line.

---

## 10. Error Code Reference

Every code the transfers, funding, and accounts endpoints can return.
Switch on these strings — never on HTTP status alone, and never on the
message.

### Transfers

Covers both `POST /transfers/quote` and `POST /transfers` — not every
endpoint returns every code below; see Section 5 and Section 7 for which codes apply
to which one.

| Code | HTTP | Meaning | Suggested UX |
|---|---|---|---|
| `USER_NOT_FOUND` | 404 | Sender's profile is missing. Shouldn't happen for an authenticated request — documented for completeness. | Re-route to onboarding if this ever surfaces. |
| `RECIPIENT_NOT_FOUND` | 404 | Tag resolves to no user | "No one found with that @tag. Check the spelling." |
| `SELF_TRANSFER` | 422 | Sender is the recipient | "You can't send money to yourself." |
| `AMOUNT_INVALID` | 422 | Amount below minimum or malformed | "Minimum transfer is 1.00." |
| `CORRIDOR_UNSUPPORTED` | 422 | No FX corridor for the pair | "Transfers to this currency aren't supported yet." |
| `INSUFFICIENT_BALANCE` | 422 | Balance can't cover total debit | "You need X more to send this." |
| `PIN_INVALID` | 422 | Wrong PIN (counts toward lockout) | "Incorrect PIN. N attempts remaining." |
| `PIN_LOCKED` | 429 | Too many wrong attempts | "PIN locked. Try again in 20 minutes." |
| `DUPLICATE_TRANSFER` | 409 | Key already used, original settled | Show the original receipt (see Section 8) |
| `RATE_UNAVAILABLE` | 502 | FX provider unreachable, cache too stale | "Rate unavailable. Try again in a moment." (retry-able) |
| `FX_PROVIDER_UNAVAILABLE` | 502 | FX provider rejected the request (auth/quota) | Same message to the user. Log it — the backend needs to see these. |
| `VALIDATION_ERROR` | 422 | Request body invalid | Show `details.fields` inline |
| `INTERNAL_ERROR` | 500/502 | Server or ledger error | Retry with the same idempotency key |

> **`RATE_UNAVAILABLE` vs `FX_PROVIDER_UNAVAILABLE`:** both map to 502
> and both should show the user the same "try again" message — the
> distinction is diagnostic, not user-facing. But **log the exact code
> when you see one**, because they point at different underlying
> problems: `RATE_UNAVAILABLE` usually means the provider is briefly
> down; `FX_PROVIDER_UNAVAILABLE` usually means our API key was
> rejected or the account hit a quota. A spike in the latter is a real
> incident and the backend team needs to know.

### Funding

| Code | HTTP | Meaning |
|---|---|---|
| `USER_NOT_FOUND` | 404 | User hasn't completed onboarding; can't issue a virtual account. |
| `AUTH_INVALID` | 401 | Webhook signature failed. Only reachable when the real Flutterwave provider is active. |
| `FUNDING_PROVIDER_UNAVAILABLE` | 502 | Provider can't be reached or isn't implemented. |
| `VALIDATION_ERROR` | 422 | Webhook body doesn't match the expected shape. |
| `INTERNAL_ERROR` | 500/502 | Firestore or ledger failure. |

> **Note on webhook "failures":** the webhook returns 200 for every
> well-formed event, including ones that don't credit. If the deposit
> didn't land, check `data.credited` in the response body, not the
> HTTP status. Rejections (unknown ref, stale ref, currency mismatch)
> are logged at `CRITICAL` on the backend.

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
| `PIN_ALREADY_SET` | 409 | PIN already set — returned by `POST /users/me/pin` |
| `PIN_INVALID` | 422 | Wrong PIN — returned by `POST /users/me/pin/verify` and by transfer execute |
| `PIN_LOCKED` | 429 | Locked — returned by `POST /users/me/pin/verify` and by transfer execute |
| `PHONE_MISMATCH` | 422 | Returned by `POST /users/me/pin/reset` when the token's phone claim is missing or doesn't match the stored phone |

> **Note on `POST /users/me/pin/reset`:** this endpoint's error
> surface is narrower than the PIN set/verify endpoints. Its only
> documented failure mode is `PHONE_MISMATCH` (the endpoint requires
> a phone-verified token and compares the token's `phone_number`
> claim against the profile's stored phone). It does **not** return
> `PIN_ALREADY_SET`, `PIN_INVALID`, or `PIN_LOCKED` — it clears the
> PIN unconditionally once the phone check passes. Verify against the
> implementation before relying on this in the client.

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
| POST | `/api/v1/funding/virtual-account` | Get or create virtual account |
| POST | `/api/v1/webhooks/flutterwave` | Receive deposit webhook |
| POST | `/api/v1/transfers/quote` | Price a transfer |
| POST | `/api/v1/transfers` | Execute a transfer |
| GET | `/api/v1/transactions` | List transaction history |
| GET | `/api/v1/transactions/{transaction_id}` | Fetch a single transaction |
| GET | `/api/v1/transfers/{transaction_id}` | Fetch a receipt **(planned — use `/transactions/{id}` for now)** |
| POST | `/api/v1/withdrawals` | Withdraw to bank/mobile money **(planned)** |

**That's 21 live endpoints and 2 planned ones.**

Note: the transactions endpoints are live and can be used today —
`GET /api/v1/transactions/{transaction_id}` returns the same receipt
data that `GET /api/v1/transfers/{transaction_id}` was planned to
return, and is scoped to the caller's participation. Use it for the
receipt screen.

---

**Questions?** Ping the backend engineer with:

1. The exact request (method, URL, headers, body)
2. The exact response (status, body)
3. The `error.code` value
4. The approximate timestamp

That's everything needed to trace the request through the logs.