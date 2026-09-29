# Nova AI — Flutter Integration Guide

**Audience:** the Flutter developer building Nova's chat and natural-language send screens.
**Companion doc:** `docs/api-contract.md` is the source of truth for every endpoint, including plain `/transfers` and `/transfers/scheduled`. This guide covers only the three `/ai/*` endpoints and how to wire them into Flutter. Where an error is shared with the plain transfer flow (`PIN_INVALID`, `INSUFFICIENT_BALANCE`, ...), this guide points back to the main contract.

**By the end of this guide you will have:**
- The exact request and response JSON for all three endpoints.
- Copy-paste Dart: models, API client, error mapper, PIN dialog, chat screen, dedicated send screen, and an "Upcoming transfers" card.
- A step-by-step recipe for each transfer flow (A, B, C).
- One master error table and a testing checklist.
- A short list of questions to confirm with the backend (Section 12).

---

## 0. Read this first

### 0.1 What changed since the previous version of this doc

| # | Change | What you must do |
|---|---|---|
| 1 | `POST /ai/execute-transfer` **no longer accepts `text`**. It takes structured fields. | Send `recipient_tag`, `amount_minor`, `confirmed_recipient_uid`, `execute_at`, `idempotency_key`, `pin`. |
| 2 | `confirmed_recipient_uid` is now **required**. | Always pass the uid you showed the user. |
| 3 | `idempotency_key` is now **required** (8–128 chars). | Generate a UUIDv4 per attempt (rules in Section 8.3). |
| 4 | `/ai/ask` `TRANSFER_INTENT` used to say "tap Send money". It now returns a full `confirm_transfer` payload. | React to `data.action == "confirm_transfer"`: open the PIN dialog, then call execute. |
| 5 | New transfer flow, **Flow C (chat-native send)**. | Recommended flow. |
| 6 | New `/ai/ask` kind `SCHEDULED_TRANSFERS` (kinds went from nine to **ten**). | Handle it, optionally render a card. |
| 7 | Error `RECIPIENT_CONFIRMATION_MISMATCH` was renamed **`RECIPIENT_CHANGED`** (still HTTP 409). | Update any string comparisons. |
| 8 | The `TRANSFER_INTENT` bubble text is written by Gemini and varies. | Never cache, compare, or parse `answer`. Use `data.intent`. |
| 9 | `amount_minor` on execute must be **at least 100** (minimum transfer). | Validate client-side, still handle `AMOUNT_INVALID`. |

### 0.2 Five-minute mental model

```
/ai/parse-transfer   sentence  ->  preview (intent + quote).            No money moves.
/ai/ask              question  ->  answer about the user's money,
                                   OR a transfer confirmation payload.  No money moves.
/ai/execute-transfer structured fields + PIN  ->  settles or schedules.  Money moves.
```

Only `/ai/execute-transfer` moves money. It never calls Gemini and never re-parses text, so the amount and recipient that settle are exactly what the user saw.

### 0.3 Suggested file layout

```
lib/
  api/
    api_exception.dart
    api_client.dart
    nova_api_client.dart
  models/
    nova_models.dart
  utils/
    format.dart
  flows/
    collect_pin_and_execute.dart
  widgets/
    pin_entry_dialog.dart
    upcoming_transfers_card.dart
  screens/
    nova_chat_screen.dart       # Flow C (recommended)
    nova_send_screen.dart       # Flow B
```

---

## Table of contents

1. [What Nova is](#1-what-nova-is)
2. [Setup and conventions](#2-setup-and-conventions)
3. [Endpoint 1: `POST /ai/parse-transfer`](#3-endpoint-1-post-aiparse-transfer)
4. [Endpoint 2: `POST /ai/execute-transfer`](#4-endpoint-2-post-aiexecute-transfer)
5. [Endpoint 3: `POST /ai/ask`](#5-endpoint-3-post-aiask)
6. [The three transfer flows](#6-the-three-transfer-flows)
7. [Dart models](#7-dart-models)
8. [Dart API layer](#8-dart-api-layer)
9. [Dart UI building blocks](#9-dart-ui-building-blocks)
10. [Master error reference](#10-master-error-reference)
11. [Testing checklist](#11-testing-checklist)
12. [Open questions to confirm with backend](#12-open-questions-to-confirm-with-backend)
13. [Gotchas](#13-gotchas)

---

## 1. What Nova is

Nova does two things.

1. **Turns a typed sentence into a transfer.** "send 5000 to david.ng" becomes an immediate or scheduled transfer.
2. **Answers questions about the user's own money** ("what's my balance", "who did I send to last", "did my scheduled payment go out") using their real ledger data, never invented numbers.

Nova is not a general chatbot. Off-topic questions get a warm decline.

`/ai/ask` can also *begin* a transfer. If the user types "send 500 to david.ng" in the chat, Nova parses it, quotes it, and returns a structured payload so the UI can collect a PIN and finish without leaving the chat.

---

## 2. Setup and conventions

### 2.1 Base URL, auth, headers

```
Base URL:     https://novabanq-api.onrender.com/api/v1
Auth:         Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

### 2.2 Response envelope (all endpoints)

```json
{ "success": true,  "data": { ... }, "error": null }
```

```json
{ "success": false, "data": null,
  "error": { "code": "PIN_INVALID", "message": "…", "details": {} } }
```

### 2.3 Conventions you will rely on

| Topic | Rule |
|---|---|
| **Money** | Every money field ending in `_minor` is an **integer in minor units** (`150000` = 1,500.00). Never use `double` for money. |
| **Display strings** | `intent.amount_major` (parse-transfer only) is display-only. Do not do math on it. |
| **Times** | ISO 8601 UTC (`2026-09-28T17:00:00.000Z`, or `+00:00` offset). `DateTime.parse` handles both. Call `.toLocal()` before showing. |
| **Latency** | Nova calls go through Gemini. Budget **1–3 seconds**. Always show a typing indicator or spinner, and set the client timeout to about 30 s. |
| **Statelessness** | `/ai/ask` takes only `{ "question": "…" }`. Do not expect Nova to remember earlier turns ("and last month?" will not work). |
| **Gemini prose** | `answer` on `TRANSFER_INTENT` (and other kinds) varies between runs. Display it; never compare or parse it. |
| **Minor-unit precision** | The Dart helpers in this guide assume 2 minor digits (true for GHS and NGN). Check the contract before adding other currencies. |

### 2.4 pubspec dependencies

```yaml
dependencies:
  http: ^1.2.0
  uuid: ^4.4.0
  firebase_auth: any   # you already have this
```

The `dart:io` import in the API client is not available on Flutter Web. If you ship Web, drop the `SocketException` catch.

---

## 3. Endpoint 1: `POST /ai/parse-transfer`

**Purpose:** turn a sentence into a transfer *preview*. No money moves, no PIN, nothing is scheduled. Safe to call repeatedly.

**Use it for:** the dedicated "Send with Nova" screen (Flows A/B).

### Request

```json
{ "text": "send 5000 to david.ng" }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | The user's raw instruction, 1–500 characters. |

### Response (200)

```json
{
  "success": true,
  "data": {
    "intent": {
      "action": "transfer",
      "amount_major": "5000",
      "recipient_tag": "david.ng",
      "execute_at": null
    },
    "quote": {
      "sender_currency": "GHS",
      "recipient": {
        "uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2",
        "tag": "david.ng",
        "display_name": "David Chinedu",
        "country": "NG",
        "currency": "NGN"
      },
      "send_amount_minor": 500000,
      "fee_minor": 5000,
      "total_debit_minor": 505000,
      "receive_amount_minor": 57134100,
      "rate": "114.268226",
      "expires_at": "2026-09-28T15:03:25.182Z"
    },
    "requested_text": "send 5000 to david.ng"
  },
  "error": null
}
```

Reading that example: the sender sends GHS 5,000.00, pays a GHS 50.00 fee, is debited GHS 5,050.00, and the recipient gets NGN 571,341.00.

| Field | Type | Notes |
|---|---|---|
| `intent.action` | string | Always `"transfer"` on success. |
| `intent.amount_major` | string | Amount in **major units** (`"5000"`, `"19.99"`), preserving the user's input. **Display-only.** For anything computational use `quote.*_minor`. (Parse defensively, see Section 12, Q1.) |
| `intent.recipient_tag` | string | Normalized (lowercase, no leading `@`). |
| `intent.execute_at` | string? | ISO 8601 UTC if the user asked for a future time, else `null`. **This is your immediate-vs-scheduled signal.** |
| `quote` | object | Same shape as `POST /transfers/quote` in the main contract. |
| `requested_text` | string | Echo of what you sent. Good for "You said: …". |

### Errors

| HTTP | Code | Meaning | UX |
|---|---|---|---|
| 422 | `VALIDATION_ERROR` | Text couldn't be understood as a transfer. | Show `error.message` **verbatim**; it's already user-facing ("Please include who you're sending to"). |
| 404 | `RECIPIENT_NOT_FOUND` | Tag resolves to no user. | Same as plain transfer flow. |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor for the pair. | Same as plain transfer flow. |
| 502 | `INTERNAL_ERROR` | Gemini unreachable. | "Nova is unavailable right now. Try again, or use the regular Send screen." |
| 502 | `RATE_UNAVAILABLE` / `FX_PROVIDER_UNAVAILABLE` | FX provider issue. | Same as plain transfer flow. |

Messages you may see in `VALIDATION_ERROR`: "I couldn't understand that as a transfer request", "Please include who you're sending to", "Please include an amount", "I couldn't read the amount", "Amount isn't valid for GHS", "I couldn't understand the time you specified". **Do not write your own copy; show the backend's message.**

> **Distinguishing a parse failure from a malformed body:** both are 422 `VALIDATION_ERROR`. A malformed body always has `details.fields` populated. A parse failure has it empty or absent. Check `details.fields` first (the `ApiException.isIntentParseFailure` getter in Section 8.1 does this).

---

## 4. Endpoint 2: `POST /ai/execute-transfer`

**Purpose:** execute (or schedule) a transfer the user has already confirmed.

- It **does not** re-parse natural language and **does not** call Gemini.
- Every field comes from a confirmation payload you got from `/ai/ask` or `/ai/parse-transfer`.
- **Why no `text` field:** a second Gemini parse could, even at temperature 0, settle a different amount than the user was shown. Sending the already-computed fields removes that risk.
- **The PIN is a separate field.** It never touches the model and is verified like `POST /transfers`.

### Request

```json
{
  "recipient_tag": "david.ng",
  "amount_minor": 500000,
  "confirmed_recipient_uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2",
  "execute_at": null,
  "idempotency_key": "01HZX8V5K2N3P4Q5R6S7T8U9V0",
  "pin": "48392"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `recipient_tag` | string | yes | Full @tag exactly as returned by the confirmation step. A leading `@` is accepted and stripped. |
| `amount_minor` | int | yes | Sender-currency minor units. Must match the confirmation payload **and be at least 100** (the platform minimum transfer). |
| `confirmed_recipient_uid` | string | yes | The recipient uid the user was shown. The backend re-resolves the tag at execute time and rejects with `RECIPIENT_CHANGED` if it no longer resolves to this uid. This is the core safety check. |
| `execute_at` | string? | no | ISO 8601 UTC for a scheduled transfer. `null` or omitted means immediate. |
| `idempotency_key` | string | yes | Client-generated, unique per attempt, 8–128 chars. A retry with the same key returns the original result without settling twice. |
| `pin` | string | yes | Exactly 5 digits. |

### Response (201): discriminated by `kind`

Both arms are always present; one is populated and the other is `null`. **Branch on `data.kind` first.**

**Immediate:**

```json
{
  "success": true,
  "data": {
    "kind": "IMMEDIATE",
    "transfer": {
      "transaction_id": "1b9a1064-43f9-4581-b092-72261fe3c0ee",
      "status": "SETTLED",
      "quote": { "...": "same shape as POST /transfers/quote" },
      "settled_at": "2026-09-28T15:03:12.501Z"
    },
    "scheduled_transfer": null
  },
  "error": null
}
```

**Scheduled:**

```json
{
  "success": true,
  "data": {
    "kind": "SCHEDULED",
    "transfer": null,
    "scheduled_transfer": {
      "scheduled_transfer_id": "8f2e1a90-...",
      "recipient_tag": "david.ng",
      "recipient_display_name": "David Chinedu",
      "amount_minor": 500000,
      "sender_currency": "GHS",
      "execute_at": "2026-09-28T17:00:00.000Z",
      "status": "PENDING",
      "transaction_id": null,
      "failure_reason": null,
      "created_at": "2026-09-28T15:03:12.501Z"
    }
  },
  "error": null
}
```

### Errors

This endpoint never parses text, so parse errors don't apply. It reuses the main contract's error surface for the money movement.

| HTTP | Code | Meaning | UX |
|---|---|---|---|
| 409 | `RECIPIENT_CHANGED` | The tag now resolves to a different uid than `confirmed_recipient_uid`. | "That tag now points to a different account. Please start again." **Discard the confirmation and re-preview.** Never retry with the same uid. |
| 404 | `RECIPIENT_NOT_FOUND` | Tag no longer resolves. | Same as plain flow. |
| 422 | `PIN_INVALID` | Wrong PIN. | Re-open the PIN dialog with an error (Section 9.3). |
| 429 | `PIN_LOCKED` | Too many wrong PINs. | Show `error.message`. |
| 422 | `INSUFFICIENT_BALANCE` | Can't cover total debit. | Same as plain flow. |
| 422 | `SELF_TRANSFER` | Sender equals recipient. | Same as plain flow. |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor. | Same as plain flow. |
| 422 | `AMOUNT_INVALID` | Below the minimum (100 minor units) or otherwise rejected. | Same as plain flow. |
| 422 | `VALIDATION_ERROR` (with `details.fields`) | Malformed body (bad PIN format, short idempotency key…). | This is a client bug; log it, show a generic error. |
| 502 | `RATE_UNAVAILABLE` / `FX_PROVIDER_UNAVAILABLE` | FX provider issue. | Same as plain flow. |
| 409 | `DUPLICATE_TRANSFER` | Should **not** occur here (a repeated idempotency key returns the original result). | If you ever see it, tell the backend team. |

Full detail on the shared codes is in `docs/api-contract.md`, Section 10.

---

## 5. Endpoint 3: `POST /ai/ask`

**Purpose:** answer a plain-language question about the user's own money, grounded in real ledger data. Read-only: no PIN, no money movement. It also *starts* transfers when the user types a transfer instruction.

### Request

```json
{ "question": "what's my balance" }
```

The question length limit isn't documented. Keep it under 500 characters to be safe.

### Response (200)

```json
{
  "success": true,
  "data": {
    "kind": "BALANCE",
    "answer": "You've got GHS 1,240.50 sitting pretty in your account, David.",
    "data": { "balance_minor": 124050, "currency": "GHS" }
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `kind` | string | One of ten values (below). Unknown future values should fall back to `UNKNOWN`. |
| `answer` | string | Render as a chat bubble as-is. |
| `data` | object? | Structured numbers behind the answer, or `null`. For most kinds you can ignore it. **For `TRANSFER_INTENT` you must act on it.** |

### The ten `kind` values

| Kind | Example question | `data`? | Frontend action |
|---|---|---|---|
| `GREETING` | "hello", "bye" | no | Show `answer`. |
| `BALANCE` | "what's my balance" | yes | Show `answer` (optionally a balance card). |
| `LAST_RECIPIENT` | "who did I send to last" | yes | Show `answer`. |
| `SPENDING_SUMMARY` | "how much did I spend last month" | yes | Show `answer`. |
| `COUNTERPARTY_DETAILS` | "tell me about chidera" | yes | Show `answer`. |
| `SPENDING_ADVICE` | "am I spending too much" | yes | Show `answer`. |
| `SCHEDULED_TRANSFERS` | "did my scheduled payment go out", "what's pending" | yes | Show `answer`, optionally the Upcoming-transfers card. |
| `GENERAL_FINANCE` | "how can I save money" | no | Show `answer`. |
| `TRANSFER_INTENT` | "send 200 to david.ng" | yes (or `null`) | **Branch:** if `data.action == "confirm_transfer"`, open the PIN dialog. |
| `UNKNOWN` | anything off-topic | no | Show `answer`. |

### 5.1 `TRANSFER_INTENT`: the chat-native send payload

When the parse succeeds:

```json
{
  "success": true,
  "data": {
    "kind": "TRANSFER_INTENT",
    "answer": "David, I'll send GH₵1,500.00 to Habeeb Olanrewaju Muhammed (@olanrewaju.ng). Enter your PIN to confirm.",
    "data": {
      "action": "confirm_transfer",
      "intent": {
        "recipient_tag": "olanrewaju.ng",
        "recipient_display_name": "Habeeb Olanrewaju Muhammed",
        "recipient_uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2",
        "amount_minor": 150000,
        "sender_currency": "GHS",
        "fee_minor": 1500,
        "total_debit_minor": 151500,
        "receive_amount_minor": 17135010,
        "rate": "114.233400",
        "execute_at": null,
        "original_text": "send 1500 cedis to olanrewaju.ng"
      }
    }
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `data.action` | string | Always `"confirm_transfer"` here. **Your trigger** for the PIN dialog. |
| `data.intent.recipient_tag` | string | Normalized tag. Send as `recipient_tag` on execute. |
| `data.intent.recipient_display_name` | string | Safe to show. |
| `data.intent.recipient_uid` | string | Send as `confirmed_recipient_uid` on execute. **Required.** |
| `data.intent.amount_minor` | int | Send amount, sender currency, minor units. |
| `data.intent.sender_currency` | string | e.g. `"GHS"`. |
| `data.intent.fee_minor` | int | Fee. |
| `data.intent.total_debit_minor` | int | What leaves the sender's balance. |
| `data.intent.receive_amount_minor` | int | What the recipient gets, in *their* currency. (Their currency code isn't in this payload.) |
| `data.intent.rate` | string | FX rate applied. |
| `data.intent.execute_at` | string? | Non-null means scheduled. |
| `data.intent.original_text` | string | User's verbatim message. |

**Immediate vs. scheduled:** the execute call is identical. With `execute_at == null` the backend returns `kind: "IMMEDIATE"`. With a value it returns `kind: "SCHEDULED"`.

### 5.2 `TRANSFER_INTENT` with an incomplete instruction

If the user types "send to david.ng" (no amount) or "schedule a payment to david.ng" (no amount or time), `data` is `null` and `answer` is a help sentence ("Please include an amount…", "Happy to schedule that, I just need to know how much to send and when…").

- Show it as a **normal Nova bubble**.
- **Do not open the PIN dialog.** Check `data?['action'] == 'confirm_transfer'`. The `AskResponse.isTransferConfirmation` getter does this for you.
- Backend docs disagree on whether this arrives as HTTP 200 with `data: null` or as 422 `VALIDATION_ERROR`. The code in this guide handles **both** (Section 12, Q2).

### 5.3 `SCHEDULED_TRANSFERS` payload

```json
{
  "schedules": [
    {
      "scheduled_transfer_id": "98ef1f2a-...",
      "recipient_tag": "david.ng",
      "recipient_display_name": "Eze David Chinedu",
      "amount_minor": 50000,
      "sender_currency": "GHS",
      "amount_display": "GH₵500.00",
      "status": "PENDING",
      "transaction_id": null,
      "failure_reason": null,
      "execute_at": "2026-09-29T18:50:00+00:00",
      "created_at": "2026-09-29T18:46:09.419298+00:00"
    }
  ],
  "count": 1,
  "pending_count": 1,
  "settled_count": 0,
  "truncated": false
}
```

| Field | Type | Notes |
|---|---|---|
| `schedules` | list | Caller's scheduled transfers, newest first. |
| `schedules[].status` | string | `PENDING`, `SETTLED`, `FAILED`, or `CANCELLED`. |
| `schedules[].transaction_id` | string? | Set once settled. `null` while pending, and also `null` for failed or cancelled schedules (an attempt that doesn't settle writes nothing to the ledger). |
| `schedules[].failure_reason` | string? | Only on `FAILED`. |
| `schedules[].execute_at` | string? | `null` if the underlying document lacks it. |
| `schedules[].amount_display` | string | Pre-formatted, e.g. `GH₵500.00`. Safe to show. |
| `count` / `pending_count` / `settled_count` | int | Totals. |
| `truncated` | bool | `true` means the fetch hit the cap; the list is a floor, not the full set. Say "at least N" in any UI that shows counts. |

### 5.4 Errors

| HTTP | Code | Meaning | UX |
|---|---|---|---|
| 502 | `INTERNAL_ERROR` | Gemini unreachable **and** the question needed real data (balance, spending, schedules, transfer parse). | "Nova can't check that right now. Try again in a moment." **Show it as a real error.** Do not fake a friendly fallback. |
| 502 | `INTERNAL_ERROR` | Firestore down while fetching data. | Same. |
| 404 | `RECIPIENT_NOT_FOUND` | From the transfer-parse path. | Same as plain flow. |
| 422 | `CORRIDOR_UNSUPPORTED` / `SELF_TRANSFER` / `AMOUNT_INVALID` | From the transfer-parse path. | Same as plain flow. |

**Why some failures are silent and some aren't:** for `GREETING` and `UNKNOWN`, if Gemini is briefly down the backend returns a canned friendly line (no account data was at stake). For everything else it returns a real 502 rather than guess. Treat a 502 as a real failure. Never retry it silently.

---

## 6. The three transfer flows

| Flow | Where | Steps | When to use |
|---|---|---|---|
| **A** | Dedicated screen | parse, PIN sheet showing the quote, execute | Fewest taps. |
| **B** | Dedicated screen | parse, **explicit preview screen**, PIN, execute | Higher-stakes or default for a Send screen. |
| **C** | Chat | ask, PIN modal, execute | **Recommended.** User never leaves the chat. |

All three end in the same `POST /ai/execute-transfer` call with the same required fields.

### Flow C: chat-native send (recommended)

```
User types "send 5000 to david.ng" in the chat
        |
        v
POST /ai/ask { question }
        |
        +-- kind == TRANSFER_INTENT and data.action == "confirm_transfer"
        |       1. Append `answer` as a Nova bubble
        |       2. Open PIN modal (5 digits, masked)
        |       3. Generate a fresh idempotency_key for this PIN submission
        |       4. POST /ai/execute-transfer {
        |            recipient_tag           = intent.recipient_tag
        |            amount_minor            = intent.amount_minor
        |            confirmed_recipient_uid = intent.recipient_uid
        |            execute_at              = intent.execute_at
        |            idempotency_key         = <uuid>
        |            pin                     = <collected>
        |          }
        |       5. switch on data.kind
        |            IMMEDIATE -> "Done. Sent to <name>." + transaction id
        |            SCHEDULED -> "Scheduled for <local time>."
        |       6. On error: PIN_INVALID -> re-open dialog with error
        |                    others      -> error bubble
        |
        +-- anything else -> append `answer` as a normal bubble (NO PIN dialog)
```

**Why it's recommended:** one place, no navigation; the PIN goes into a modal and never into chat text; the `confirmed_recipient_uid` check still applies; scheduling works identically.

### Flow B: dedicated screen with explicit preview

```
1. User types a sentence on the Send-with-Nova screen
2. POST /ai/parse-transfer { text }
3. Show preview:
     To: David Chinedu (@david.ng)
     You send: GH₵5,000.00   Fee: GH₵50.00   Total: GH₵5,050.00
     They get: about ₦571,341.00   Rate: 114.268226
     (If intent.execute_at != null: "Scheduled for <local time>")
4. User taps Confirm -> PIN dialog
5. POST /ai/execute-transfer {
     recipient_tag           = quote.recipient.tag
     amount_minor            = quote.send_amount_minor
     confirmed_recipient_uid = quote.recipient.uid
     execute_at              = intent.execute_at
     idempotency_key         = <uuid>
     pin                     = <collected>
   }
6. switch on data.kind and show your existing receipt / scheduled screen
```

### Flow A: fast path

Same as B but skip the separate preview screen: parse, then open the PIN sheet directly with the quote summary displayed inside it (the provided `PinEntryDialog` already shows recipient, amount, fee, and total). **Never skip showing the recipient name**; the name is the user's chance to catch a wrong tag.

---

## 7. Dart models

Copy into `lib/models/nova_models.dart`. Requires Dart 3 (sealed classes, pattern matching). No code generation.

```dart
// lib/models/nova_models.dart

int _asInt(dynamic v) => (v as num).toInt();

// ---------------------------------------------------------------------
// Shared: quote + recipient (skip if you already have these from /transfers)
// ---------------------------------------------------------------------

class RecipientSummary {
  final String uid;
  final String tag;
  final String displayName;
  final String country;
  final String currency;

  RecipientSummary({
    required this.uid,
    required this.tag,
    required this.displayName,
    required this.country,
    required this.currency,
  });

  factory RecipientSummary.fromJson(Map<String, dynamic> json) =>
      RecipientSummary(
        uid: json['uid'] as String,
        tag: json['tag'] as String,
        displayName: json['display_name'] as String,
        country: json['country'] as String,
        currency: json['currency'] as String,
      );
}

class QuoteResponse {
  final String senderCurrency;
  final RecipientSummary recipient;
  final int sendAmountMinor;
  final int feeMinor;
  final int totalDebitMinor;
  final int receiveAmountMinor;
  final String rate;
  final DateTime expiresAt;

  QuoteResponse({
    required this.senderCurrency,
    required this.recipient,
    required this.sendAmountMinor,
    required this.feeMinor,
    required this.totalDebitMinor,
    required this.receiveAmountMinor,
    required this.rate,
    required this.expiresAt,
  });

  factory QuoteResponse.fromJson(Map<String, dynamic> json) => QuoteResponse(
        senderCurrency: json['sender_currency'] as String,
        recipient: RecipientSummary.fromJson(
          json['recipient'] as Map<String, dynamic>,
        ),
        sendAmountMinor: _asInt(json['send_amount_minor']),
        feeMinor: _asInt(json['fee_minor']),
        totalDebitMinor: _asInt(json['total_debit_minor']),
        receiveAmountMinor: _asInt(json['receive_amount_minor']),
        rate: json['rate'] as String,
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );
}

class TransferResponse {
  final String transactionId;
  final String status;
  final QuoteResponse quote;
  final DateTime settledAt;

  TransferResponse({
    required this.transactionId,
    required this.status,
    required this.quote,
    required this.settledAt,
  });

  factory TransferResponse.fromJson(Map<String, dynamic> json) =>
      TransferResponse(
        transactionId: json['transaction_id'] as String,
        status: json['status'] as String,
        quote: QuoteResponse.fromJson(json['quote'] as Map<String, dynamic>),
        settledAt: DateTime.parse(json['settled_at'] as String),
      );
}

class ScheduledTransferResponse {
  final String scheduledTransferId;
  final String recipientTag;
  final String? recipientDisplayName;
  final int amountMinor;
  final String senderCurrency;
  final DateTime executeAt;
  final String status;
  final String? transactionId;
  final String? failureReason;
  final DateTime createdAt;

  ScheduledTransferResponse({
    required this.scheduledTransferId,
    required this.recipientTag,
    required this.recipientDisplayName,
    required this.amountMinor,
    required this.senderCurrency,
    required this.executeAt,
    required this.status,
    required this.transactionId,
    required this.failureReason,
    required this.createdAt,
  });

  factory ScheduledTransferResponse.fromJson(Map<String, dynamic> json) =>
      ScheduledTransferResponse(
        scheduledTransferId: json['scheduled_transfer_id'] as String,
        recipientTag: json['recipient_tag'] as String,
        recipientDisplayName: json['recipient_display_name'] as String?,
        amountMinor: _asInt(json['amount_minor']),
        senderCurrency: json['sender_currency'] as String,
        executeAt: DateTime.parse(json['execute_at'] as String),
        status: json['status'] as String,
        transactionId: json['transaction_id'] as String?,
        failureReason: json['failure_reason'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

// ---------------------------------------------------------------------
// /ai/parse-transfer
// ---------------------------------------------------------------------

class ParsedIntent {
  final String action;

  /// Display-only, major units (e.g. "5000", "19.99"). Never do math on it.
  final String amountMajor;
  final String recipientTag;

  /// null == immediate, non-null == scheduled.
  final DateTime? executeAt;

  ParsedIntent({
    required this.action,
    required this.amountMajor,
    required this.recipientTag,
    required this.executeAt,
  });

  factory ParsedIntent.fromJson(Map<String, dynamic> json) => ParsedIntent(
        action: json['action'] as String,
        // .toString() tolerates the backend sending either "5000" or 5000.
        amountMajor: json['amount_major'].toString(),
        recipientTag: json['recipient_tag'] as String,
        executeAt: json['execute_at'] == null
            ? null
            : DateTime.parse(json['execute_at'] as String),
      );

  bool get isScheduled => executeAt != null;
}

class ParseIntentResponse {
  final ParsedIntent intent;
  final QuoteResponse quote;
  final String requestedText;

  ParseIntentResponse({
    required this.intent,
    required this.quote,
    required this.requestedText,
  });

  factory ParseIntentResponse.fromJson(Map<String, dynamic> json) =>
      ParseIntentResponse(
        intent: ParsedIntent.fromJson(json['intent'] as Map<String, dynamic>),
        quote: QuoteResponse.fromJson(json['quote'] as Map<String, dynamic>),
        requestedText: json['requested_text'] as String,
      );
}

// ---------------------------------------------------------------------
// TransferIntentPayload: the ONE type both flows use to execute a transfer.
//   - Flow C builds it from /ai/ask  (TransferIntentPayload.fromJson)
//   - Flow A/B build it from /ai/parse-transfer (TransferIntentPayload.fromParse)
// ---------------------------------------------------------------------

class TransferIntentPayload {
  final String recipientTag;
  final String recipientDisplayName;
  final String recipientUid;
  final int amountMinor;
  final String senderCurrency;
  final int feeMinor;
  final int totalDebitMinor;
  final int receiveAmountMinor;
  final String rate;

  /// null == immediate, non-null == scheduled.
  final DateTime? executeAt;
  final String originalText;

  TransferIntentPayload({
    required this.recipientTag,
    required this.recipientDisplayName,
    required this.recipientUid,
    required this.amountMinor,
    required this.senderCurrency,
    required this.feeMinor,
    required this.totalDebitMinor,
    required this.receiveAmountMinor,
    required this.rate,
    required this.executeAt,
    required this.originalText,
  });

  factory TransferIntentPayload.fromJson(Map<String, dynamic> json) =>
      TransferIntentPayload(
        recipientTag: json['recipient_tag'] as String,
        recipientDisplayName: json['recipient_display_name'] as String,
        recipientUid: json['recipient_uid'] as String,
        amountMinor: _asInt(json['amount_minor']),
        senderCurrency: json['sender_currency'] as String,
        feeMinor: _asInt(json['fee_minor']),
        totalDebitMinor: _asInt(json['total_debit_minor']),
        receiveAmountMinor: _asInt(json['receive_amount_minor']),
        rate: json['rate'] as String,
        executeAt: json['execute_at'] == null
            ? null
            : DateTime.parse(json['execute_at'] as String),
        originalText: json['original_text'] as String,
      );

  factory TransferIntentPayload.fromParse(ParseIntentResponse r) =>
      TransferIntentPayload(
        recipientTag: r.quote.recipient.tag,
        recipientDisplayName: r.quote.recipient.displayName,
        recipientUid: r.quote.recipient.uid,
        amountMinor: r.quote.sendAmountMinor,
        senderCurrency: r.quote.senderCurrency,
        feeMinor: r.quote.feeMinor,
        totalDebitMinor: r.quote.totalDebitMinor,
        receiveAmountMinor: r.quote.receiveAmountMinor,
        rate: r.quote.rate,
        executeAt: r.intent.executeAt,
        originalText: r.requestedText,
      );

  bool get isScheduled => executeAt != null;
}

// ---------------------------------------------------------------------
// /ai/execute-transfer: discriminated result
//
// Both arms exist on the wire (one null). This wrapper exposes only the
// populated one, and Dart 3 forces exhaustive switches.
// ---------------------------------------------------------------------

sealed class ExecuteTransferResult {
  const ExecuteTransferResult();

  static ExecuteTransferResult fromJson(Map<String, dynamic> json) {
    final kind = json['kind'] as String;
    switch (kind) {
      case 'IMMEDIATE':
        return ImmediateTransferResult(
          transfer: TransferResponse.fromJson(
            json['transfer'] as Map<String, dynamic>,
          ),
        );
      case 'SCHEDULED':
        return ScheduledTransferResult(
          scheduledTransfer: ScheduledTransferResponse.fromJson(
            json['scheduled_transfer'] as Map<String, dynamic>,
          ),
        );
      default:
        throw FormatException('Unknown execute-transfer kind: $kind');
    }
  }
}

class ImmediateTransferResult extends ExecuteTransferResult {
  final TransferResponse transfer;
  const ImmediateTransferResult({required this.transfer});
}

class ScheduledTransferResult extends ExecuteTransferResult {
  final ScheduledTransferResponse scheduledTransfer;
  const ScheduledTransferResult({required this.scheduledTransfer});
}

// Usage:
//   switch (result) {
//     case ImmediateTransferResult(:final transfer):
//       showReceipt(transfer);
//     case ScheduledTransferResult(:final scheduledTransfer):
//       showScheduledConfirmation(scheduledTransfer);
//   }

// ---------------------------------------------------------------------
// /ai/ask
// ---------------------------------------------------------------------

enum AskKind {
  greeting,
  balance,
  lastRecipient,
  spendingSummary,
  counterpartyDetails,
  spendingAdvice,
  scheduledTransfers,
  generalFinance,
  transferIntent,
  unknown;

  static AskKind fromApiString(String value) {
    switch (value) {
      case 'GREETING':
        return AskKind.greeting;
      case 'BALANCE':
        return AskKind.balance;
      case 'LAST_RECIPIENT':
        return AskKind.lastRecipient;
      case 'SPENDING_SUMMARY':
        return AskKind.spendingSummary;
      case 'COUNTERPARTY_DETAILS':
        return AskKind.counterpartyDetails;
      case 'SPENDING_ADVICE':
        return AskKind.spendingAdvice;
      case 'SCHEDULED_TRANSFERS':
        return AskKind.scheduledTransfers;
      case 'GENERAL_FINANCE':
        return AskKind.generalFinance;
      case 'TRANSFER_INTENT':
        return AskKind.transferIntent;
      default:
        return AskKind.unknown;
    }
  }
}

class AskResponse {
  final AskKind kind;
  final String answer;
  final Map<String, dynamic>? data;

  AskResponse({required this.kind, required this.answer, required this.data});

  factory AskResponse.fromJson(Map<String, dynamic> json) => AskResponse(
        kind: AskKind.fromApiString(json['kind'] as String),
        answer: json['answer'] as String,
        data: json['data'] as Map<String, dynamic>?,
      );

  /// True only when the PIN dialog should open.
  /// Incomplete instructions ("send to david.ng") have data == null -> false.
  bool get isTransferConfirmation =>
      kind == AskKind.transferIntent &&
      data != null &&
      data!['action'] == 'confirm_transfer';

  /// Typed confirmation payload, or null if this isn't a confirmation.
  TransferIntentPayload? get transferIntent => isTransferConfirmation
      ? TransferIntentPayload.fromJson(data!['intent'] as Map<String, dynamic>)
      : null;

  /// Typed schedule list, or null if this isn't a SCHEDULED_TRANSFERS reply.
  ScheduledTransfersData? get scheduledTransfers =>
      kind == AskKind.scheduledTransfers && data != null
          ? ScheduledTransfersData.fromJson(data!)
          : null;
}

// ---------------------------------------------------------------------
// /ai/ask: SCHEDULED_TRANSFERS payload
// ---------------------------------------------------------------------

class ScheduledTransferSummary {
  final String scheduledTransferId;
  final String recipientTag;
  final String? recipientDisplayName;
  final int amountMinor;
  final String senderCurrency;
  final String amountDisplay; // pre-formatted by backend, e.g. "GH₵500.00"
  final String status; // PENDING | SETTLED | FAILED | CANCELLED
  final String? transactionId;
  final String? failureReason;
  final DateTime? executeAt;
  final DateTime? createdAt;

  ScheduledTransferSummary({
    required this.scheduledTransferId,
    required this.recipientTag,
    required this.recipientDisplayName,
    required this.amountMinor,
    required this.senderCurrency,
    required this.amountDisplay,
    required this.status,
    required this.transactionId,
    required this.failureReason,
    required this.executeAt,
    required this.createdAt,
  });

  factory ScheduledTransferSummary.fromJson(Map<String, dynamic> json) =>
      ScheduledTransferSummary(
        scheduledTransferId: json['scheduled_transfer_id'] as String,
        recipientTag: json['recipient_tag'] as String,
        recipientDisplayName: json['recipient_display_name'] as String?,
        amountMinor: _asInt(json['amount_minor']),
        senderCurrency: json['sender_currency'] as String,
        amountDisplay: json['amount_display'] as String,
        status: json['status'] as String,
        transactionId: json['transaction_id'] as String?,
        failureReason: json['failure_reason'] as String?,
        executeAt: json['execute_at'] == null
            ? null
            : DateTime.parse(json['execute_at'] as String),
        createdAt: json['created_at'] == null
            ? null
            : DateTime.parse(json['created_at'] as String),
      );

  bool get isPending => status == 'PENDING';
  bool get isSettled => status == 'SETTLED';
  bool get isFailed => status == 'FAILED';
  bool get isCancelled => status == 'CANCELLED';
}

class ScheduledTransfersData {
  final List<ScheduledTransferSummary> schedules;
  final int count;
  final int pendingCount;
  final int settledCount;

  /// true => the list is a floor, not the full set.
  final bool truncated;

  ScheduledTransfersData({
    required this.schedules,
    required this.count,
    required this.pendingCount,
    required this.settledCount,
    required this.truncated,
  });

  factory ScheduledTransfersData.fromJson(Map<String, dynamic> json) =>
      ScheduledTransfersData(
        schedules: (json['schedules'] as List<dynamic>)
            .map((e) =>
                ScheduledTransferSummary.fromJson(e as Map<String, dynamic>))
            .toList(),
        count: _asInt(json['count']),
        pendingCount: _asInt(json['pending_count']),
        settledCount: _asInt(json['settled_count']),
        truncated: json['truncated'] as bool,
      );
}
```

---

## 8. Dart API layer

### 8.1 `lib/api/api_exception.dart`

```dart
// lib/api/api_exception.dart

class ApiException implements Exception {
  /// HTTP status. 0 means we never got an HTTP response (offline, timeout).
  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;

  const ApiException({
    required this.statusCode,
    required this.code,
    required this.message,
    this.details = const {},
  });

  const ApiException.network([String message = 'Network error'])
      : this(statusCode: 0, code: 'NETWORK_ERROR', message: message);

  bool get isNetworkError => statusCode == 0;
  bool get isServerError => statusCode >= 500;

  bool get hasFieldErrors {
    final f = details['fields'];
    if (f is List) return f.isNotEmpty;
    if (f is Map) return f.isNotEmpty;
    return false;
  }

  /// 422 VALIDATION_ERROR with empty details.fields == "the backend couldn't
  /// read that as a transfer". The message is user-facing: show it as-is.
  bool get isIntentParseFailure =>
      statusCode == 422 && code == 'VALIDATION_ERROR' && !hasFieldErrors;

  @override
  String toString() => 'ApiException($statusCode $code: $message)';
}

extension ApiExceptionMessages on ApiException {
  /// User-facing copy. Pass `executing: true` for /ai/execute-transfer, where
  /// an ambiguous failure must tell the user to check their history before
  /// retrying (money may have moved).
  String userMessage({bool executing = false}) {
    if (isNetworkError) {
      return executing
          ? "I couldn't confirm whether that went through. "
              "Please check your transaction history before trying again."
          : "Can't reach Nova. Check your connection and try again.";
    }
    switch (code) {
      case 'PIN_INVALID':
        return "That PIN didn't match. Try again.";
      case 'PIN_LOCKED':
        return message.isNotEmpty
            ? message
            : 'Too many wrong PIN attempts. Please try again later.';
      case 'INSUFFICIENT_BALANCE':
        return "You don't have enough balance for that transfer.";
      case 'RECIPIENT_CHANGED':
        return "The account behind that tag has changed since you confirmed, "
            "so I stopped the transfer. Please start again.";
      case 'AMOUNT_INVALID':
        return message.isNotEmpty
            ? message
            : "That amount isn't allowed. The minimum transfer is 1.00.";
    }
    if (isServerError) {
      return executing
          ? "Something went wrong on our side. Please check your transaction "
              "history before trying again."
          : "Nova can't check that right now. Try again in a moment.";
    }
    return message; // backend messages are already user-facing
  }
}
```

### 8.2 `lib/api/api_client.dart`: reference implementation

If you already have a client that attaches the Firebase token and unwraps the envelope, keep it and just make sure it throws `ApiException` with the fields above. Otherwise use this:

```dart
// lib/api/api_client.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io'; // SocketException (not available on Flutter Web)

import 'package:http/http.dart' as http;

import 'api_exception.dart';

class ApiClient {
  ApiClient({
    required this.baseUrl, // 'https://novabanq-api.onrender.com/api/v1'
    required this.getToken, // () => FirebaseAuth.instance.currentUser?.getIdToken()
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 30),
  }) : _http = httpClient ?? http.Client();

  final String baseUrl;
  final Future<String?> Function() getToken;
  final Duration timeout;
  final http.Client _http;

  /// POSTs JSON and returns the envelope's `data` object.
  /// Throws [ApiException] on any failure.
  Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final token = await getToken();

    final http.Response res;
    try {
      res = await _http
          .post(
            Uri.parse('$baseUrl$path'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
            // NEVER log this body: on /ai/execute-transfer it contains the PIN.
            body: jsonEncode(body),
          )
          .timeout(timeout);
    } on TimeoutException {
      throw const ApiException.network('Request timed out');
    } on SocketException {
      throw const ApiException.network('No connection');
    } on http.ClientException {
      throw const ApiException.network('Connection failed');
    }

    Map<String, dynamic>? envelope;
    try {
      envelope = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    } catch (_) {
      // Non-JSON body (e.g. a gateway HTML error page). Fall through.
    }

    if (envelope != null && envelope['success'] == true) {
      return (envelope['data'] as Map).cast<String, dynamic>();
    }

    final err = (envelope?['error'] as Map?)?.cast<String, dynamic>();
    throw ApiException(
      statusCode: res.statusCode,
      code: (err?['code'] as String?) ?? 'UNKNOWN',
      message: (err?['message'] as String?) ?? 'Something went wrong.',
      details: (err?['details'] as Map?)?.cast<String, dynamic>() ?? const {},
    );
  }
}
```

> Token expiry: `getIdToken()` returns a cached token and refreshes automatically when it is near expiry. A 401 is covered by the main contract; the usual handling is `getIdToken(true)` and one retry.

### 8.3 `lib/api/nova_api_client.dart`

```dart
// lib/api/nova_api_client.dart

import '../models/nova_models.dart';
import 'api_client.dart';

class NovaApiClient {
  NovaApiClient(this._client);
  final ApiClient _client;

  /// Preview a natural-language transfer. No money moves.
  Future<ParseIntentResponse> parseTransfer(String text) async {
    final data = await _client.post('/ai/parse-transfer', {'text': text});
    return ParseIntentResponse.fromJson(data);
  }

  /// Ask Nova a question about the user's money (or start a transfer).
  Future<AskResponse> ask(String question) async {
    final data = await _client.post('/ai/ask', {'question': question});
    return AskResponse.fromJson(data);
  }

  /// Execute a confirmed transfer. MONEY MOVES.
  ///
  /// [idempotencyKey] is supplied by the caller (not generated here) so the
  /// caller controls when a key is reused:
  ///   - NEW key for every fresh user submission (including each PIN retry).
  ///   - SAME key only when re-sending the identical request because the
  ///     outcome was unknown (timeout / connection dropped).
  Future<ExecuteTransferResult> executeTransfer({
    required TransferIntentPayload intent,
    required String pin,
    required String idempotencyKey,
  }) async {
    final body = <String, dynamic>{
      'recipient_tag': intent.recipientTag,
      'amount_minor': intent.amountMinor,
      'confirmed_recipient_uid': intent.recipientUid,
      'execute_at': intent.executeAt?.toUtc().toIso8601String(),
      'idempotency_key': idempotencyKey,
      'pin': pin,
    };
    final data = await _client.post('/ai/execute-transfer', body);
    return ExecuteTransferResult.fromJson(data);
  }
}
```

**Idempotency-key rules (important):**

| Situation | Key |
|---|---|
| User taps Confirm with a PIN | New UUIDv4 |
| Wrong PIN, user re-enters | New UUIDv4 (the earlier attempt did not settle) |
| Request timed out or connection dropped, you don't know if it landed | **Reuse the same key** when re-sending the identical request. If it did settle, you get the original result back instead of a double payment. |
| User starts a brand-new transfer | New UUIDv4 |

### 8.4 `lib/utils/format.dart`

```dart
// lib/utils/format.dart

const _symbols = {'GHS': 'GH₵', 'NGN': '₦'};

/// 150000, 'GHS'  ->  'GH₵1,500.00'   (assumes 2 minor digits)
String formatMinor(int minor, String currency) {
  final negative = minor < 0;
  final abs = minor.abs();
  final whole = (abs ~/ 100).toString().replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'),
        (_) => ',',
      );
  final frac = (abs % 100).toString().padLeft(2, '0');
  final symbol = _symbols[currency] ?? '$currency ';
  return '${negative ? '-' : ''}$symbol$whole.$frac';
}

const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/// Converts to local time and formats like '29 Sep 2026, 19:50'.
String formatLocalDateTime(DateTime dt) {
  final l = dt.toLocal();
  final hh = l.hour.toString().padLeft(2, '0');
  final mm = l.minute.toString().padLeft(2, '0');
  return '${l.day} ${_months[l.month - 1]} ${l.year}, $hh:$mm';
}
```

---

## 9. Dart UI building blocks

### 9.1 `lib/widgets/pin_entry_dialog.dart`

Modal, masked, one-shot. The PIN is returned to the caller and sent straight to `/ai/execute-transfer`. It is never written to chat history, logs, or Nova.

```dart
// lib/widgets/pin_entry_dialog.dart

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/nova_models.dart';
import '../utils/format.dart';

class PinEntryDialog extends StatefulWidget {
  const PinEntryDialog({super.key, required this.intent, this.errorText});

  final TransferIntentPayload intent;

  /// Shown under the field, e.g. after a wrong PIN.
  final String? errorText;

  /// Returns the 5-digit PIN, or null if cancelled.
  static Future<String?> show(
    BuildContext context, {
    required TransferIntentPayload intent,
    String? errorText,
  }) {
    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => PinEntryDialog(intent: intent, errorText: errorText),
    );
  }

  @override
  State<PinEntryDialog> createState() => _PinEntryDialogState();
}

class _PinEntryDialogState extends State<PinEntryDialog> {
  final _pin = TextEditingController();

  @override
  void dispose() {
    _pin.dispose();
    super.dispose();
  }

  void _submit() {
    if (_pin.text.length == 5) Navigator.of(context).pop(_pin.text);
  }

  @override
  Widget build(BuildContext context) {
    final i = widget.intent;
    final cur = i.senderCurrency;
    final theme = Theme.of(context);

    return AlertDialog(
      title: const Text('Enter PIN to confirm'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'To: ${i.recipientDisplayName} (@${i.recipientTag})',
            style: theme.textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          Text('Amount: ${formatMinor(i.amountMinor, cur)}'),
          Text('Fee: ${formatMinor(i.feeMinor, cur)}'),
          Text(
            'Total debit: ${formatMinor(i.totalDebitMinor, cur)}',
            style: theme.textTheme.bodyMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
          if (i.executeAt != null) ...[
            const SizedBox(height: 4),
            Text('Scheduled for ${formatLocalDateTime(i.executeAt!)}'),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: _pin,
            autofocus: true,
            obscureText: true,
            enableSuggestions: false,
            autocorrect: false,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(5),
            ],
            decoration: InputDecoration(
              labelText: 'PIN',
              counterText: '',
              errorText: widget.errorText,
              border: const OutlineInputBorder(),
            ),
            onSubmitted: (_) => _submit(),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(null),
          child: const Text('Cancel'),
        ),
        ValueListenableBuilder<TextEditingValue>(
          valueListenable: _pin,
          builder: (_, value, __) => FilledButton(
            onPressed: value.text.length == 5 ? _submit : null,
            child: const Text('Confirm'),
          ),
        ),
      ],
    );
  }
}
```

### 9.2 `lib/widgets/upcoming_transfers_card.dart`

Optional card to render under a `SCHEDULED_TRANSFERS` bubble.

```dart
// lib/widgets/upcoming_transfers_card.dart

import 'package:flutter/material.dart';

import '../models/nova_models.dart';
import '../utils/format.dart';

class UpcomingTransfersCard extends StatelessWidget {
  const UpcomingTransfersCard({super.key, required this.data});
  final ScheduledTransfersData data;

  @override
  Widget build(BuildContext context) {
    if (data.schedules.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(top: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              data.truncated
                  ? 'Scheduled transfers (showing latest)'
                  : 'Scheduled transfers',
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            for (final s in data.schedules) _Row(s: s),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.s});
  final ScheduledTransferSummary s;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (label, color) = switch (s.status) {
      'PENDING' => ('Pending', scheme.primary),
      'SETTLED' => ('Sent', Colors.green),
      'FAILED' => ('Failed', scheme.error),
      'CANCELLED' => ('Cancelled', scheme.outline),
      _ => (s.status, scheme.outline),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${s.amountDisplay} to ${s.recipientDisplayName ?? '@${s.recipientTag}'}',
                ),
                if (s.executeAt != null)
                  Text(
                    formatLocalDateTime(s.executeAt!),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                if (s.isFailed && s.failureReason != null)
                  Text(
                    s.failureReason!,
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: scheme.error),
                  ),
              ],
            ),
          ),
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
```

### 9.3 `lib/flows/collect_pin_and_execute.dart`

One helper used by **every** flow. It owns the PIN loop and the idempotency-key rules, so screens don't reimplement them.

- Opens the PIN dialog.
- On `PIN_INVALID`, re-opens it with an inline error, using a **new** key.
- On a network/timeout error, retries **once** with the **same** key (outcome unknown).
- Returns `null` if the user cancels.
- Throws `ApiException` for everything else.

```dart
// lib/flows/collect_pin_and_execute.dart

import 'package:flutter/widgets.dart';
import 'package:uuid/uuid.dart';

import '../api/api_exception.dart';
import '../api/nova_api_client.dart';
import '../models/nova_models.dart';
import '../widgets/pin_entry_dialog.dart';

const _uuid = Uuid();

Future<ExecuteTransferResult?> collectPinAndExecute({
  required BuildContext context,
  required NovaApiClient api,
  required TransferIntentPayload intent,
  void Function(bool busy)? onBusyChanged,
}) async {
  String? pinError;

  while (true) {
    if (!context.mounted) return null;
    final pin = await PinEntryDialog.show(
      context,
      intent: intent,
      errorText: pinError,
    );
    if (pin == null) return null; // cancelled

    // New user submission => new key.
    final key = _uuid.v4();
    onBusyChanged?.call(true);
    try {
      try {
        return await api.executeTransfer(
          intent: intent,
          pin: pin,
          idempotencyKey: key,
        );
      } on ApiException catch (e) {
        if (!e.isNetworkError) rethrow;
        // Outcome unknown: re-send the IDENTICAL request with the SAME key.
        // If the first one settled, we get the original result back.
        return await api.executeTransfer(
          intent: intent,
          pin: pin,
          idempotencyKey: key,
        );
      }
    } on ApiException catch (e) {
      if (e.code == 'PIN_INVALID') {
        pinError = "That PIN didn't match. Try again.";
        continue; // loop: re-open dialog
      }
      rethrow; // PIN_LOCKED, INSUFFICIENT_BALANCE, RECIPIENT_CHANGED, ...
    } finally {
      onBusyChanged?.call(false);
    }
  }
}
```

### 9.4 `lib/screens/nova_chat_screen.dart`: Flow C

```dart
// lib/screens/nova_chat_screen.dart

import 'package:flutter/material.dart';

import '../api/api_exception.dart';
import '../api/nova_api_client.dart';
import '../flows/collect_pin_and_execute.dart';
import '../models/nova_models.dart';
import '../utils/format.dart';
import '../widgets/upcoming_transfers_card.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final bool isError;
  final ScheduledTransfersData? scheduled; // optional card under the bubble

  const ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
    this.scheduled,
  });
}

class NovaChatScreen extends StatefulWidget {
  const NovaChatScreen({super.key, required this.api});
  final NovaApiClient api;

  @override
  State<NovaChatScreen> createState() => _NovaChatScreenState();
}

class _NovaChatScreenState extends State<NovaChatScreen> {
  final _controller = TextEditingController();
  final _messages = <ChatMessage>[];
  bool _busy = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _add(ChatMessage m) {
    if (mounted) setState(() => _messages.add(m));
  }

  void _setBusy(bool v) {
    if (mounted) setState(() => _busy = v);
  }

  Future<void> _send() async {
    final question = _controller.text.trim();
    if (question.isEmpty || _busy) return;

    _controller.clear();
    _add(ChatMessage(text: question, isUser: true));
    _setBusy(true);

    try {
      final r = await widget.api.ask(question);

      // 1. Always show Nova's prose.
      _add(ChatMessage(
        text: r.answer,
        isUser: false,
        scheduled: r.scheduledTransfers, // null unless SCHEDULED_TRANSFERS
      ));

      // 2. Only a real confirmation opens the PIN dialog.
      final intent = r.transferIntent; // null for help messages / other kinds
      if (intent != null) {
        _setBusy(false); // don't show the typing dots behind the modal
        await _confirmAndExecute(intent);
      }
    } on ApiException catch (e) {
      if (e.isIntentParseFailure) {
        // Backend's "Please include an amount" etc. Not an error: a Nova reply.
        _add(ChatMessage(text: e.message, isUser: false));
      } else {
        _add(ChatMessage(text: e.userMessage(), isUser: false, isError: true));
      }
    } catch (_) {
      _add(const ChatMessage(
        text: 'Something unexpected happened. Please try again.',
        isUser: false,
        isError: true,
      ));
    } finally {
      _setBusy(false);
    }
  }

  Future<void> _confirmAndExecute(TransferIntentPayload intent) async {
    try {
      final result = await collectPinAndExecute(
        context: context,
        api: widget.api,
        intent: intent,
        onBusyChanged: _setBusy,
      );

      if (result == null) {
        _add(const ChatMessage(
          text: 'Cancelled. No transfer was made.',
          isUser: false,
        ));
        return;
      }

      switch (result) {
        case ImmediateTransferResult(:final transfer):
          _add(ChatMessage(
            text: '✓ Done. Sent ${formatMinor(intent.amountMinor, intent.senderCurrency)} '
                'to ${intent.recipientDisplayName}.\n'
                'Transaction ID: ${transfer.transactionId}',
            isUser: false,
          ));
        case ScheduledTransferResult(:final scheduledTransfer):
          _add(ChatMessage(
            text: '✓ Scheduled for '
                '${formatLocalDateTime(scheduledTransfer.executeAt)}.',
            isUser: false,
          ));
      }
    } on ApiException catch (e) {
      _add(ChatMessage(
        text: e.userMessage(executing: true),
        isUser: false,
        isError: true,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nova')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              reverse: true,
              itemCount: _messages.length + (_busy ? 1 : 0),
              itemBuilder: (context, index) {
                if (_busy && index == 0) return const _TypingIndicator();
                final i = _messages.length - 1 - (index - (_busy ? 1 : 0));
                return _MessageBubble(message: _messages[i]);
              },
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      enabled: !_busy,
                      textInputAction: TextInputAction.send,
                      decoration: const InputDecoration(
                        hintText: 'Ask Nova about your money…',
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: _busy ? null : _send,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});
  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final bg = message.isUser
        ? scheme.primary
        : (message.isError
            ? scheme.errorContainer
            : scheme.surfaceContainerHighest); // Flutter 3.22+; use surfaceVariant on older
    final fg = message.isUser
        ? scheme.onPrimary
        : (message.isError ? scheme.onErrorContainer : scheme.onSurface);

    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.8,
        ),
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(message.text, style: TextStyle(color: fg)),
              if (message.scheduled != null)
                UpcomingTransfersCard(data: message.scheduled!),
            ],
          ),
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Align(
          alignment: Alignment.centerLeft,
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
}
```

### 9.5 `lib/screens/nova_send_screen.dart`: Flow B

```dart
// lib/screens/nova_send_screen.dart

import 'package:flutter/material.dart';

import '../api/api_exception.dart';
import '../api/nova_api_client.dart';
import '../flows/collect_pin_and_execute.dart';
import '../models/nova_models.dart';
import '../utils/format.dart';

class NovaSendScreen extends StatefulWidget {
  const NovaSendScreen({super.key, required this.api});
  final NovaApiClient api;

  @override
  State<NovaSendScreen> createState() => _NovaSendScreenState();
}

class _NovaSendScreenState extends State<NovaSendScreen> {
  final _controller = TextEditingController();
  ParseIntentResponse? _preview;
  String? _error;
  String? _success;
  bool _loading = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _parse() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;
    setState(() {
      _loading = true;
      _error = null;
      _success = null;
      _preview = null;
    });
    try {
      final p = await widget.api.parseTransfer(text);
      if (mounted) setState(() => _preview = p);
    } on ApiException catch (e) {
      // For parse failures e.message is already user-facing.
      if (mounted) setState(() => _error = e.userMessage());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _confirm() async {
    final preview = _preview;
    if (preview == null || _loading) return;
    final intent = TransferIntentPayload.fromParse(preview);

    try {
      final result = await collectPinAndExecute(
        context: context,
        api: widget.api,
        intent: intent,
        onBusyChanged: (b) {
          if (mounted) setState(() => _loading = b);
        },
      );
      if (!mounted || result == null) return; // cancelled

      final msg = switch (result) {
        ImmediateTransferResult(:final transfer) =>
          'Sent. Transaction ID: ${transfer.transactionId}',
        ScheduledTransferResult(:final scheduledTransfer) =>
          'Scheduled for ${formatLocalDateTime(scheduledTransfer.executeAt)}',
      };
      // In your app: push your existing receipt / scheduled-confirmation screen.
      setState(() {
        _success = msg;
        _preview = null;
        _controller.clear();
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.userMessage(executing: true));
      // RECIPIENT_CHANGED: the preview is stale. Discard it and re-parse.
      if (e.code == 'RECIPIENT_CHANGED') setState(() => _preview = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _preview;
    return Scaffold(
      appBar: AppBar(title: const Text('Send with Nova')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _controller,
            enabled: !_loading,
            decoration: const InputDecoration(
              hintText: 'e.g. send 5000 to david.ng at 6pm',
              border: OutlineInputBorder(),
            ),
            onSubmitted: (_) => _parse(),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _loading ? null : _parse,
            child: _loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Preview'),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (_success != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_success!),
            ),
          if (p != null) ...[
            const SizedBox(height: 16),
            _PreviewCard(p: p),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _loading ? null : _confirm,
              child: Text(p.intent.isScheduled ? 'Confirm & schedule' : 'Confirm & send'),
            ),
          ],
        ],
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({required this.p});
  final ParseIntentResponse p;

  @override
  Widget build(BuildContext context) {
    final q = p.quote;
    final cur = q.senderCurrency;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('You said: "${p.requestedText}"',
                style: Theme.of(context).textTheme.bodySmall),
            const Divider(height: 24),
            Text('To: ${q.recipient.displayName} (@${q.recipient.tag})',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('You send: ${formatMinor(q.sendAmountMinor, cur)}'),
            Text('Fee: ${formatMinor(q.feeMinor, cur)}'),
            Text('Total debit: ${formatMinor(q.totalDebitMinor, cur)}'),
            const SizedBox(height: 8),
            // "about": the execute request carries no quote id/rate (Section 12, Q4).
            Text('They get about ${formatMinor(q.receiveAmountMinor, q.recipient.currency)}'),
            Text('Rate: ${q.rate}',
                style: Theme.of(context).textTheme.bodySmall),
            if (p.intent.executeAt != null) ...[
              const SizedBox(height: 8),
              Text('Scheduled for ${formatLocalDateTime(p.intent.executeAt!)}',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ],
        ),
      ),
    );
  }
}
```

### 9.6 Wiring it together

```dart
final apiClient = ApiClient(
  baseUrl: 'https://novabanq-api.onrender.com/api/v1',
  getToken: () async => FirebaseAuth.instance.currentUser?.getIdToken(),
);
final nova = NovaApiClient(apiClient);

// Recommended entry point (Flow C):
Navigator.of(context).push(MaterialPageRoute(builder: (_) => NovaChatScreen(api: nova)));
```

---

## 10. Master error reference

Shared transfer errors are defined in `docs/api-contract.md`, Section 10. "Where" shows which `/ai/*` endpoints can return each code.

| HTTP | `error.code` | Where | Meaning | What to do |
|---|---|---|---|---|
| 422 | `VALIDATION_ERROR` (empty `details.fields`) | parse-transfer; ask (transfer path, see Q2) | Sentence couldn't be read as a transfer | Show `error.message` verbatim. In chat, render as a Nova bubble. |
| 422 | `VALIDATION_ERROR` (populated `details.fields`) | all | Malformed request body | Client bug. Log it, show a generic error. |
| 404 | `RECIPIENT_NOT_FOUND` | parse, ask, execute | Tag resolves to nobody | Same as plain flow. |
| 409 | `RECIPIENT_CHANGED` | execute | Tag now resolves to a different uid | Discard the confirmation; re-preview. Never retry with the same uid. |
| 422 | `PIN_INVALID` | execute | Wrong PIN | Re-open PIN dialog with error (handled by `collectPinAndExecute`). |
| 429 | `PIN_LOCKED` | execute | Too many wrong PINs | Show `error.message`. |
| 422 | `INSUFFICIENT_BALANCE` | execute | Can't cover total debit | Same as plain flow. |
| 422 | `SELF_TRANSFER` | ask, execute | Sender equals recipient | Same as plain flow. |
| 422 | `CORRIDOR_UNSUPPORTED` | parse, ask, execute | No FX corridor | Same as plain flow. |
| 422 | `AMOUNT_INVALID` | ask, execute | Below minimum (100 minor units) or invalid | Same as plain flow. |
| 502 | `RATE_UNAVAILABLE` / `FX_PROVIDER_UNAVAILABLE` | parse, execute | FX provider down | Same as plain flow. |
| 502 | `INTERNAL_ERROR` | all | Gemini or Firestore unavailable | Show a real error. **Do not silently retry.** On execute, tell the user to check history before retrying. |
| 409 | `DUPLICATE_TRANSFER` | plain `/transfers` only | Duplicate | Should not appear on execute; report to backend if it does. |
| n/a | (client) network error | all | No HTTP response | On execute: retry once with the **same** idempotency key, then tell the user to check history. |

**Reading 409:** on `/ai/execute-transfer` a 409 `RECIPIENT_CHANGED` is the "tag changed hands" error. A 409 from plain `/transfers` is `DUPLICATE_TRANSFER`. Always read `error.code`, never the status alone.

---

## 11. Testing checklist

Run against a live backend.

| # | Try this | Expect | Verifies |
|---|---|---|---|
| 1 | Chat: "send 100 to david.ng" | Nova confirmation, PIN modal, then "Done" with transaction id | Flow C end-to-end; `confirmed_recipient_uid` round-trip |
| 2 | Send screen: same text | Preview shows name, amounts, fee, total; confirm; PIN; result | Flow B end-to-end |
| 3 | "send 100 to david.ng at 6pm" (either flow) | `kind: SCHEDULED`, `status: PENDING`, future `execute_at` | Discriminated result branch |
| 4 | "send money" | Message: "Please include who you're sending to" | Specific backend message, not generic copy |
| 5 | "send to david.ng" (no amount) in **chat** | A Nova bubble with the help text; **no PIN dialog** | Incomplete-parse branch (both 200/null and 422 shapes) |
| 6 | "send to david.ng" on **Send screen** | 422 `VALIDATION_ERROR` shown inline | Parse error path |
| 7 | "schedule a payment to david.ng" | "Happy to schedule that…" help bubble, no PIN dialog | Schedule-aware help |
| 8 | Wrong PIN | Dialog re-opens with inline "That PIN didn't match"; second try works | PIN loop, new idempotency key |
| 9 | Repeated wrong PINs | `PIN_LOCKED` message shown | Lockout path |
| 10 | Send an amount below 1.00 (100 minor) | `AMOUNT_INVALID` message | Minimum-amount handling |
| 11 | Send more than balance | `INSUFFICIENT_BALANCE` | Shared error path |
| 12 | Send to yourself | `SELF_TRANSFER` | Shared error path |
| 13 | Double-tap Confirm quickly | Only one transfer created | No double-submit (dialog pops on first tap; input disabled while busy) |
| 14 | Go offline right after tapping Confirm, then back online | One retry with the same key; result is the original transfer, never two | Idempotency on unknown outcome |
| 15 | Reassign a tag between confirm and PIN (ask backend to help) | 409 `RECIPIENT_CHANGED`, "start again" message, no money moved | Core safety check |
| 16 | "what's my balance" | `BALANCE`, matches `/accounts/me` | Grounded data |
| 17 | "who did I send to last" | `LAST_RECIPIENT` matches history | Grounded data |
| 18 | "did my scheduled payment go out" / "what's pending" | `SCHEDULED_TRANSFERS`; card renders; `pending_count` correct | New kind |
| 19 | "hello" three times | Three different replies | Greeting isn't hard-coded |
| 20 | "what's the capital of France" | `UNKNOWN` or brief `GENERAL_FINANCE` decline | Stays on-topic |
| 21 | Device offline, send "what's my balance" | "Can't reach Nova" error bubble | Client network error path |
| 22 | Backend simulates Gemini outage: balance question | 502 shown as a real error | Not accidentally made "soft" |
| 23 | Backend simulates Gemini outage: "hello" | Friendly canned reply, no error | Not accidentally made "hard" |
| 24 | Inspect logs and network inspector | PIN never appears in app logs | PIN hygiene |

Rows 22 and 23 need the backend to simulate a Gemini outage. Turning off your own network can't test them.

---

## 12. Open questions to confirm with backend

The source docs were inconsistent on these points. The code above is written to work either way, but please confirm and delete the ones that are settled.

| # | Question | How this guide handles it |
|---|---|---|
| Q1 | Is `intent.amount_major` a **string** (`"5000"`) or a plain decimal **number** on the wire? One changelog line says number, the field docs and example say string. | `ParsedIntent` uses `.toString()`, so both work. |
| Q2 | For an incomplete instruction typed into `/ai/ask` ("send to david.ng"), is the help message a **200** with `data: null` (Section 5.2) or a **422 `VALIDATION_ERROR`** (as the error tables imply)? | The chat screen handles both (`isTransferConfirmation` and `isIntentParseFailure`). |
| Q3 | Does replaying a **failed** attempt's idempotency key return the cached failure? | Fresh key for every PIN attempt; reuse only on unknown outcome. |
| Q4 | Does execute honor the previewed rate, or re-quote? The request carries no quote id or rate. | UI says "they get about …". |
| Q5 | What is the exact PIN lockout duration? An earlier draft said 20 minutes. | UI shows `error.message` from `PIN_LOCKED`. |
| Q6 | Is there a max length on `/ai/ask` `question`? (Documented only for `/ai/parse-transfer`: 500.) | Keep under 500. |
| Q7 | Does the `TRANSFER_INTENT` payload include the recipient's currency code? Only `receive_amount_minor` is present. | Chat UI doesn't display the receive amount; Flow B does, using `quote.recipient.currency`. |

---

## 13. Gotchas

- **Never log the PIN.** It's a plain field on the execute request. Make sure any HTTP logging interceptor redacts request bodies (or at least `pin`) and the `Authorization` header.
- **Never put the PIN in chat text.** It goes in the modal and straight to execute. Gemini never sees it.
- **Don't cache, compare, or parse `answer`.** It's Gemini prose and varies. Use `data.intent` for logic.
- **Only `data.action == "confirm_transfer"` opens the PIN dialog.** Check `data?['action']`, not just `kind == TRANSFER_INTENT`.
- **`execute_at != null` is your only immediate-vs-scheduled signal.** Use it to choose copy ("Send now" vs "Schedule for …").
- **`confirmed_recipient_uid` is mandatory and must be the uid the user was shown.** Never look it up again yourself at execute time; that defeats the check.
- **`RECIPIENT_CHANGED` means stop and start over.** Never auto-retry.
- **Idempotency keys:** new key per user submission; same key only to re-send an identical request after an unknown outcome. Never reuse a key across different amounts or recipients.
- **Minor units everywhere, except `intent.amount_major`.** It's a display string; don't mix it into calculations.
- **Branch on `data.kind` before touching either arm** of the execute response.
- **Don't treat every non-200 the same.** A 502 from `/ai/*` is a real failure to show. A canned `GREETING`/`UNKNOWN` reply is a normal 200, not an error.
- **Ambiguous execute failures:** on a network error or 5xx from execute, don't tell the user "it failed". Money may have moved; tell them to check their history (`userMessage(executing: true)` does this).
- **Show loading states.** 1–3 s of Gemini latency with no spinner looks broken.
- **Flutter version:** `surfaceContainerHighest` needs Flutter 3.22+; on older versions use `surfaceVariant`.
- **`TRANSFER_INTENT` is not a redirect any more.** Remove any old "tap Send money" handling.