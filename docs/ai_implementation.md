# Nova AI — Flutter Integration Guide

**Audience:** The Flutter developer building the chat / natural-language
screens on top of NovaBanq's AI layer ("Nova").

**Relationship to other docs:** `docs/api-contract.md` is the contract
for every endpoint, including the plain `/transfers` and
`/transfers/scheduled` endpoints. This document is a **companion**,
focused only on the three `/ai/*` endpoints and how to wire them up in
Flutter. Where an error code is shared with the plain transfer flow
(e.g. `PIN_INVALID`, `INSUFFICIENT_BALANCE`), this doc points back to
the main contract instead of repeating it.

**What you'll have by the end of this doc:**
- The exact request/response JSON for all three endpoints.
- Ready-to-paste Dart model classes with `fromJson`.
- A ready-to-paste API client.
- A working chat-screen pattern for `/ai/ask`.
- A working parse-then-confirm-then-execute pattern for transfers.
- Every error you need to handle, and what to show the user for each.

---

## Table of Contents

1. [What Nova is, in one paragraph](#1-what-nova-is-in-one-paragraph)
2. [Setup](#2-setup)
3. [Endpoint 1 — `POST /ai/parse-transfer`](#3-endpoint-1--post-aiparse-transfer)
4. [Endpoint 2 — `POST /ai/execute-transfer`](#4-endpoint-2--post-aiexecute-transfer)
5. [Endpoint 3 — `POST /ai/ask`](#5-endpoint-3--post-aiask)
6. [The two transfer flows you can build](#6-the-two-transfer-flows-you-can-build)
7. [Full Dart models](#7-full-dart-models)
8. [Full Dart API client](#8-full-dart-api-client)
9. [Example: Nova chat screen](#9-example-nova-chat-screen)
10. [Error code reference](#10-error-code-reference)
11. [Testing checklist](#11-testing-checklist)
12. [Gotchas — read this before you ship](#12-gotchas--read-this-before-you-ship)

---

## 1. What Nova is, in one paragraph

Nova does two things. **It turns a typed sentence into a transfer** —
"send 5000 to david.ng" becomes a real transfer or a scheduled one.
**It answers questions about the user's own money** — "what's my
balance", "who did I send to last" — using their real ledger data,
never invented numbers. Three endpoints cover this: one previews a
transfer, one executes it, one answers questions. None of them are a
general chatbot — off-topic questions get a warm decline, not a made-up
answer.

---

## 2. Setup

All three endpoints sit under the same base path and auth scheme as
everything else in the app:

```
Base URL:    https://novabanq-api.onrender.com/api/v1
Auth:        Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

Every response uses the same envelope as the rest of the API:

```json
{ "success": true, "data": { ... }, "error": null }
```

or

```json
{ "success": false, "data": null, "error": { "code": "...", "message": "...", "details": {} } }
```

**One thing specific to Nova:** these calls go through Gemini before
they hit your response. Budget for **1–3 seconds** of latency, not the
usual sub-second response you get from `/accounts/me`. Always show a
loading state — a Nova reply that takes 2 seconds with no spinner
looks broken.

---

## 3. Endpoint 1 — `POST /ai/parse-transfer`

**What it does:** turns a sentence into a transfer *preview*. No money
moves, no PIN needed, no schedule is created. Safe to call as often as
you like.

**When to call it:** the "safe" flow — see [Section 6](#6-the-two-transfer-flows-you-can-build)
— when you want to show the user who they're sending to and how much,
before asking for their PIN.

### Request

```http
POST /api/v1/ai/parse-transfer
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "text": "send 5000 to david.ng" }
```

| Field | Type | Notes |
|---|---|---|
| `text` | string | The user's raw instruction. 1–500 characters. |

### Response (200)

```json
{
  "success": true,
  "data": {
    "intent": {
      "action": "transfer",
      "amount_major": "5000.00",
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

| Field | Type | Notes |
|---|---|---|
| `intent.action` | string | Always `"transfer"` on a successful parse. |
| `intent.amount_major` | string | The amount **in major units**, as a decimal string — e.g. `"5000.00"`, not minor units. Parse it with `Decimal`/`double` carefully; treat it as display-only unless you need to recompute. |
| `intent.recipient_tag` | string | Normalized tag (lowercased, no leading `@`). |
| `intent.execute_at` | string? | ISO 8601 UTC timestamp if the user asked for a future time ("at 5pm"), otherwise `null`. **This is your signal for immediate vs. scheduled** — check it before deciding which button to show. |
| `quote` | object | Identical shape to the `POST /transfers/quote` response documented in the main API contract. Render it the same way. |
| `requested_text` | string | Echo of what you sent. Useful for showing "You said: ..." on the confirm screen. |

### Errors

| Status | Code | Meaning | Suggested UX |
|---|---|---|---|
| 422 | `INTENT_UNPARSEABLE` | The text couldn't be understood as a transfer — see the specific message | Show the message verbatim; it's already written for the user (e.g. "Please include who you're sending to") |
| 502 | `INTENT_PROVIDER_UNAVAILABLE` | Nova's model provider is unreachable | "Nova is unavailable right now — try again in a moment, or use the regular Send screen." |
| 404 | `RECIPIENT_NOT_FOUND` | The parsed tag resolves to no user | Same message as the plain transfer flow |
| 422 | `CORRIDOR_UNSUPPORTED` | No FX corridor for the pair | Same as plain transfer flow |
| 502 | `RATE_UNAVAILABLE` / `FX_PROVIDER_UNAVAILABLE` | FX provider issue | Same as plain transfer flow — see the main contract |

> **Note on `INTENT_UNPARSEABLE` messages:** the backend returns
> different messages for different problems ("I couldn't understand
> that as a transfer request", "Please include who you're sending to",
> "Please include an amount", "I couldn't read the amount", "Amount
> isn't valid for GHS"). **Display `error.message` directly** — don't
> write your own generic copy for this code. The backend's message is
> already the right thing to show.

---

## 4. Endpoint 2 — `POST /ai/execute-transfer`

**What it does:** parses the sentence **and** commits it in one call —
either as an immediate transfer or a scheduled one, depending on
whether the sentence included a future time.

**PIN is required on this call.** It never touches the model — it's a
separate field, verified the same way `POST /transfers` verifies it.

### Request

```http
POST /api/v1/ai/execute-transfer
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "text": "send 5000 to david.ng",
  "pin": "48392",
  "confirmed_recipient_uid": "RH2cWAvBQbSlCyXoI5zGxssMwPb2"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | Same instruction text. |
| `pin` | string | yes | Exactly 5 digits. |
| `confirmed_recipient_uid` | string | no | **Only set this if you already called `/ai/parse-transfer` and showed the user the recipient's name.** Pass the `uid` from that quote's `recipient.uid`. If the tag re-resolves to a *different* uid at execute time (rare — e.g. the tag was reassigned), the request is rejected instead of silently sending to someone else. Omit this field entirely for the fast path — see [Section 6](#6-the-two-transfer-flows-you-can-build). |

### Response (201) — discriminated union

The response shape depends on whether the parsed instruction included
a future time. Switch on `data.kind`.

**Immediate case:**

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
    }
  },
  "error": null
}
```

**Scheduled case** (the user said "... at 5pm" or similar):

```json
{
  "success": true,
  "data": {
    "kind": "SCHEDULED",
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

**This is the single most important thing to get right in this whole
integration: check `data.kind` before touching anything else in
`data`.** If you assume every response is `IMMEDIATE` and reach for
`data["transfer"]` on a `SCHEDULED` response, you'll get a null and a
crash. See [Section 7](#7-full-dart-models) for a Dart pattern that
makes this impossible to get wrong.

### Errors

Everything from `/ai/parse-transfer`'s error table applies here too
(the same parsing happens first), plus:

| Status | Code | Meaning | Suggested UX |
|---|---|---|---|
| 409 | `RECIPIENT_CONFIRMATION_MISMATCH` | You sent `confirmed_recipient_uid`, and it doesn't match who the tag resolves to now | "That tag now points to a different account — please review and try again." Re-run `/ai/parse-transfer` to get a fresh quote. |
| 422 | `PIN_INVALID` | Wrong PIN | Same as plain transfer flow |
| 429 | `PIN_LOCKED` | Too many wrong PINs | Same as plain transfer flow |
| 422 | `INSUFFICIENT_BALANCE` | Can't cover the total debit | Same as plain transfer flow |
| 409 | `DUPLICATE_TRANSFER` | Shouldn't normally surface here — this endpoint doesn't take a client idempotency key the way `POST /transfers` does | If you see this, it's worth flagging to backend — check whether this endpoint derives its own key internally |

> Full detail on `PIN_INVALID`, `PIN_LOCKED`, `INSUFFICIENT_BALANCE`,
> and the rest of the transfer-specific codes is in
> `docs/api-contract.md`, Section 10. This endpoint reuses that exact
> error surface for the underlying money movement — no need to
> duplicate it here.

---

## 5. Endpoint 3 — `POST /ai/ask`

**What it does:** answers a plain-language question about the user's
own money, grounded in their real ledger data. Read-only — no PIN, no
money movement, ever.

### Request

```http
POST /api/v1/ai/ask
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "question": "what's my balance" }
```

### Response (200)

```json
{
  "success": true,
  "data": {
    "kind": "BALANCE",
    "answer": "You've got GHS 1,240.50 sitting pretty in your account, David.",
    "data": {
      "balance_minor": 124050,
      "currency": "GHS"
    }
  },
  "error": null
}
```

| Field | Type | Notes |
|---|---|---|
| `kind` | string | One of nine values — see table below. Useful if you want to render some kinds differently (e.g. show a small balance card under a `BALANCE` reply), but you can ignore it entirely and just show `answer` as a chat bubble. |
| `answer` | string | Nova's natural-language reply. **Render this as-is** — it's already written to be shown directly, no further formatting needed. |
| `data` | object? | The raw numbers behind the answer, or `null`. You generally don't need this for a plain chat UI — `answer` already describes it in prose. It's there if you want to render a structured card (e.g. a mini transaction list) alongside the text reply. |

### The nine `kind` values

| Kind | Example question | Has `data`? |
|---|---|---|
| `GREETING` | "hello", "how are you", "bye" | No |
| `BALANCE` | "what's my balance" | Yes |
| `LAST_RECIPIENT` | "who did I send to last" | Yes |
| `SPENDING_SUMMARY` | "how much did I spend last month" | Yes |
| `COUNTERPARTY_DETAILS` | "tell me about chidera" | Yes |
| `SPENDING_ADVICE` | "am I spending too much" | Yes |
| `GENERAL_FINANCE` | "how can I save money" | No |
| `TRANSFER_INTENT` | "send 200 to david.ng" (typed into the ask box, not the send screen) | No |
| `UNKNOWN` | anything off-topic or unclear | No |

> **`TRANSFER_INTENT` is not an error.** If the user types a transfer
> command into the chat, Nova recognizes it and replies with something
> like *"it looks like you want to send money — tap 'Send money' and
> I'll guide you through it."* Just show `answer` like any other reply.
> You don't need to do anything special for this kind unless you want
> to add a "Go to Send" button under that specific bubble — a nice
> touch, but optional.

### Errors

| Status | Code | Meaning | Suggested UX |
|---|---|---|---|
| 502 | `ASK_PROVIDER_UNAVAILABLE` | Nova's model is unreachable **and** the question needed real data (balance, spending, etc.) | "Nova can't check that right now — try again in a moment." **Do not** show a friendly "I didn't catch that" here — the honest error is correct, because a fabricated-sounding fallback would be worse than admitting Nova is down. |
| 502 | Account/transaction lookup failure | Firestore is down while fetching the data behind the answer | Same as above |

> **Why some failures are quiet and some aren't:** for `GREETING` and
> `UNKNOWN` questions, if the model is briefly unreachable, the backend
> falls back to a static friendly line instead of erroring — those
> kinds never had real account data at stake, so a canned reply is
> fine. For everything else (balance, spending, etc.), the backend
> raises a real 502 instead of guessing. **Your UI should treat a 502
> from this endpoint as a real failure to show, not something to retry
> silently or paper over** — the backend already did the "should this
> be soft?" judgment call for you.

---

## 6. The two transfer flows you can build

Both are valid. Pick one, or offer both (e.g. fast path for typed
chat, safe path for a dedicated "Send with Nova" screen).

### Flow A — Fast path (fewest taps)

```
1. User types: "send 5000 to david.ng"
2. Ask for PIN inline (bottom sheet)
3. → POST /ai/execute-transfer   { text, pin }   (no confirmed_recipient_uid)
4. Show the result based on data.kind
```

Simplest, but the user never sees who they're sending to before the
money moves. Fine for a quick chat-style interface where the tag is
unambiguous.

### Flow B — Safe path (preview first)

```
1. User types: "send 5000 to david.ng"
2. → POST /ai/parse-transfer   { text }
3. Show: "Send GHS 5,050.00 (5000.00 + 50.00 fee) to David Chinedu
   (@david.ng)? This is ₦57,134.10 for them."
4. User taps confirm → ask for PIN
5. → POST /ai/execute-transfer   { text, pin, confirmed_recipient_uid: quote.recipient.uid }
6. Show the result based on data.kind
```

This is the flow to use for anything higher-stakes, or as your default
— it's one extra network call for a real safety net: if the tag
resolves to someone different by the time the user confirms, the
request is rejected rather than silently sent.

**Either way, always branch on `data.kind` in the final step** —
that's what tells you whether to show a settled-transfer receipt or a
"scheduled for later" confirmation.

---

## 7. Full Dart models

Copy these into `lib/models/nova_models.dart`. They assume Dart 3
(sealed classes + pattern matching) and reuse plain `fromJson`
constructors — no code generation required.

```dart
// lib/models/nova_models.dart

// ---------------------------------------------------------------------
// Shared: reuse your existing QuoteResponse / recipient models here.
// Shown inline for completeness — if you already have these from the
// plain transfer flow, don't duplicate them.
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
        sendAmountMinor: json['send_amount_minor'] as int,
        feeMinor: json['fee_minor'] as int,
        totalDebitMinor: json['total_debit_minor'] as int,
        receiveAmountMinor: json['receive_amount_minor'] as int,
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
        amountMinor: json['amount_minor'] as int,
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
  final String amountMajor; // decimal string, major units — display only
  final String recipientTag;
  final DateTime? executeAt; // null == immediate, non-null == scheduled

  ParsedIntent({
    required this.action,
    required this.amountMajor,
    required this.recipientTag,
    required this.executeAt,
  });

  factory ParsedIntent.fromJson(Map<String, dynamic> json) => ParsedIntent(
        action: json['action'] as String,
        amountMajor: json['amount_major'] as String,
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
// /ai/execute-transfer — discriminated union
//
// This is the important one. Use Dart 3's sealed classes + switch
// pattern matching so the compiler forces you to handle BOTH cases —
// there's no way to accidentally forget the SCHEDULED branch.
// ---------------------------------------------------------------------

sealed class ExecuteTransferResult {
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
  ImmediateTransferResult({required this.transfer});
}

class ScheduledTransferResult extends ExecuteTransferResult {
  final ScheduledTransferResponse scheduledTransfer;
  ScheduledTransferResult({required this.scheduledTransfer});
}

// Usage anywhere in your UI:
//
//   final result = ExecuteTransferResult.fromJson(data);
//   switch (result) {
//     case ImmediateTransferResult(:final transfer):
//       showReceipt(transfer);
//     case ScheduledTransferResult(:final scheduledTransfer):
//       showScheduledConfirmation(scheduledTransfer);
//   }
//
// The compiler will warn you (with `analyzer`'s exhaustiveness check)
// if you add a third variant later and forget to handle it here.

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
      case 'GENERAL_FINANCE':
        return AskKind.generalFinance;
      case 'TRANSFER_INTENT':
        return AskKind.transferIntent;
      default:
        return AskKind.unknown; // covers "UNKNOWN" and any surprise value
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
}
```

---

## 8. Full Dart API client

Copy into `lib/api/nova_api_client.dart`. Assumes you already have an
`ApiClient` (or similar) wrapping `http`/`dio` with the auth header and
envelope-unwrapping logic — adapt the method bodies to match whatever
that looks like in your app. `ApiException` below is a stand-in for
whatever error type your existing client throws on a non-`success`
envelope; wire it up the same way you already handle errors elsewhere.

```dart
// lib/api/nova_api_client.dart

import '../models/nova_models.dart';
import 'api_client.dart'; // your existing base client + ApiException

class NovaApiClient {
  final ApiClient _client;

  NovaApiClient(this._client);

  /// Preview a natural-language transfer instruction. No money moves.
  Future<ParseIntentResponse> parseTransfer(String text) async {
    final data = await _client.post('/ai/parse-transfer', {'text': text});
    return ParseIntentResponse.fromJson(data);
  }

  /// Parse and commit a transfer in one call. Returns either a settled
  /// transfer or a scheduled one — check the result's runtime type.
  Future<ExecuteTransferResult> executeTransfer({
    required String text,
    required String pin,
    String? confirmedRecipientUid,
  }) async {
    final body = <String, dynamic>{
      'text': text,
      'pin': pin,
      if (confirmedRecipientUid != null)
        'confirmed_recipient_uid': confirmedRecipientUid,
    };
    final data = await _client.post('/ai/execute-transfer', body);
    return ExecuteTransferResult.fromJson(data);
  }

  /// Ask Nova a question about the user's own money. Read-only.
  Future<AskResponse> ask(String question) async {
    final data = await _client.post('/ai/ask', {'question': question});
    return AskResponse.fromJson(data);
  }
}
```

---

## 9. Example: Nova chat screen

A minimal, working chat pattern for `/ai/ask`. Handles the loading
state, the happy path, and the one error case you must not paper over
(`ASK_PROVIDER_UNAVAILABLE`).

```dart
// lib/screens/nova_chat_screen.dart

import 'package:flutter/material.dart';
import '../api/nova_api_client.dart';
import '../api/api_client.dart'; // for ApiException

class ChatMessage {
  final String text;
  final bool isUser;
  ChatMessage({required this.text, required this.isUser});
}

class NovaChatScreen extends StatefulWidget {
  final NovaApiClient api;
  const NovaChatScreen({super.key, required this.api});

  @override
  State<NovaChatScreen> createState() => _NovaChatScreenState();
}

class _NovaChatScreenState extends State<NovaChatScreen> {
  final _controller = TextEditingController();
  final List<ChatMessage> _messages = [];
  bool _isWaitingForNova = false;

  Future<void> _send() async {
    final question = _controller.text.trim();
    if (question.isEmpty || _isWaitingForNova) return;

    setState(() {
      _messages.add(ChatMessage(text: question, isUser: true));
      _isWaitingForNova = true;
      _controller.clear();
    });

    try {
      final response = await widget.api.ask(question);
      setState(() {
        _messages.add(ChatMessage(text: response.answer, isUser: false));
      });
      // Optional: react to response.kind here — e.g. show a "Go to
      // Send" button under a TRANSFER_INTENT reply, or render
      // response.data as a small card under a BALANCE reply.
    } on ApiException catch (e) {
      // ASK_PROVIDER_UNAVAILABLE and Firestore-down cases land here.
      // Show this as a real failure — don't invent a friendly line;
      // the backend already decided this case deserves an honest error.
      setState(() {
        _messages.add(
          ChatMessage(
            text: "Nova can't check that right now — try again in a moment.",
            isUser: false,
          ),
        );
      });
      debugPrint('Nova ask failed: ${e.code} ${e.message}');
    } finally {
      setState(() => _isWaitingForNova = false);
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
              itemCount: _messages.length + (_isWaitingForNova ? 1 : 0),
              itemBuilder: (context, index) {
                if (_isWaitingForNova && index == 0) {
                  return const _TypingIndicator();
                }
                final message = _messages[
                    _messages.length - 1 - (index - (_isWaitingForNova ? 1 : 0))];
                return _MessageBubble(message: message);
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
                      decoration: const InputDecoration(
                        hintText: 'Ask Nova about your money…',
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: _isWaitingForNova ? null : _send,
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
  final ChatMessage message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: message.isUser
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.surfaceVariant,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          message.text,
          style: TextStyle(
            color: message.isUser
                ? Theme.of(context).colorScheme.onPrimary
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return const Padding(
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
}
```

**For the transfer flows (Flow A / Flow B from Section 6)**, reuse your
existing PIN-entry bottom sheet and receipt screen from the plain
`/transfers` implementation — the only new code is the
`ExecuteTransferResult` switch shown in Section 7, which decides
whether to push your existing receipt screen or your existing
scheduled-transfer confirmation screen.

---

## 10. Error code reference

Codes specific to the three `/ai/*` endpoints. For everything else
(PIN, balance, corridor, rate errors), see `docs/api-contract.md`,
Section 10 — these endpoints reuse that exact error surface for the
underlying transfer/quote work.

**Confirmed against the actual backend source** (`ai_intent/service.py`
and `ai_intent/ask_service.py`). Good news: nothing new needed adding
to `ErrorCode` — all four AI-specific errors reuse two existing,
generic codes. That's also the thing to watch out for: **you cannot
tell these apart from unrelated failures by `error.code` alone.** Use
the extra signals in the table below.

| Situation | HTTP | `error.code` | `error.message` | How to actually tell it apart |
|---|---|---|---|---|
| Text couldn't be parsed as a transfer | 422 | `VALIDATION_ERROR` | A specific, user-facing sentence — e.g. "Please include who you're sending to." | `details.fields` is **absent/empty**. Compare with an ordinary body-validation failure (bad JSON shape), which is also 422 `VALIDATION_ERROR` but always populates `details.fields`. **Check `details.fields` first, and only treat it as an intent-parsing failure if it's empty.** |
| Gemini unreachable during parse or execute | 502 | `INTERNAL_ERROR` | "The AI service is temporarily unavailable." | Same code as a Firestore/ledger 502 elsewhere in the app. In practice this doesn't matter — both deserve the same "try again in a moment" UI — so don't try to distinguish them; just treat any 502 from `/ai/*` as "Nova/backend is briefly down." |
| `confirmed_recipient_uid` no longer matches | **409** | `VALIDATION_ERROR` | "The recipient changed since you confirmed." | **Status code is the tell here, not the error code.** A 409 `VALIDATION_ERROR` from `/ai/execute-transfer` means this; a 409 from the plain `/transfers` endpoint means `DUPLICATE_TRANSFER` instead (different code, same status). Always read `error.code` *and* the endpoint you called together — don't assume 409 means one specific thing app-wide. |
| Gemini unreachable during `/ai/ask` | 502 | `INTERNAL_ERROR` | "The AI service is temporarily unavailable." | Same as the parse/execute case above — only fires for questions that needed real data (balance, spending, etc.); `GREETING`/`UNKNOWN` fall back to a canned reply instead of erroring, so you'll never see this specific 502 for those two kinds. |

> **One doc-accuracy note for whoever maintains `docs/api-contract.md`:**
> its Section 10 lists `VALIDATION_ERROR` as a 422-only code. It isn't,
> once the AI endpoints are in play — `RecipientConfirmationMismatchError`
> uses the exact same code string at 409. Worth a one-line addition to
> that table so the main contract doesn't quietly go stale for anyone
> not reading this companion doc.

### Recommended Dart handling

The snippet below assumes your `ApiException` (or whatever your
existing client throws — see Section 8) exposes `statusCode`, `code`,
`message`, and `detailsFields` from the envelope's `error` object. If
yours doesn't yet expose `detailsFields`, add it — it's the one field
this doc's error handling can't do without.

```dart
try {
  final result = await api.executeTransfer(text: text, pin: pin);
  // ... handle result
} on ApiException catch (e) {
  if (e.statusCode == 409 && e.code == 'VALIDATION_ERROR') {
    // Recipient confirmation mismatch — re-preview before retrying.
    showError(e.message);
    return;
  }
  if (e.statusCode == 422 &&
      e.code == 'VALIDATION_ERROR' &&
      (e.detailsFields == null || e.detailsFields!.isEmpty)) {
    // Intent couldn't be parsed — e.message is already user-facing.
    showError(e.message);
    return;
  }
  if (e.statusCode == 422) {
    // Ordinary body-validation failure — details.fields is populated.
    showFieldErrors(e.detailsFields);
    return;
  }
  if (e.statusCode >= 500) {
    showError("Nova is unavailable right now — try again in a moment.");
    return;
  }
  // Anything else (PIN_INVALID, INSUFFICIENT_BALANCE, etc.) — see
  // docs/api-contract.md Section 10 for the full shared error surface.
  showError(e.message);
}
```

---

## 11. Testing checklist

Run through this list against a live backend before calling the
integration done. Each row exercises a distinct path.

| Try this | Expect | What you're actually checking |
|---|---|---|
| "send 100 to david.ng" (Flow A) | `IMMEDIATE`, settled receipt | Fast path end-to-end |
| "send 100 to david.ng" (Flow B) | Preview shows recipient name, then settles on confirm | Safe path end-to-end, `confirmed_recipient_uid` round-trips correctly |
| "send 100 to david.ng at 6pm" | `SCHEDULED`, `status: PENDING`, `execute_at` in the future | Discriminated union takes the *other* branch correctly |
| "send money" (no recipient) | 422 `INTENT_UNPARSEABLE`, "please include who you're sending to" | Specific error message, not a generic fallback |
| Wrong PIN on execute | 422 `PIN_INVALID` | Shared error path with plain transfer flow |
| "what's my balance" | `BALANCE`, real number matching `/accounts/me` | Cross-check Nova's answer against the real balance |
| "who did I send to last" | `LAST_RECIPIENT`, real counterparty | Matches actual transaction history |
| "hello" three times in a row | Three *different* replies | Confirms the greeting isn't a hardcoded template on the happy path |
| "what's the capital of France" | `UNKNOWN` or a brief `GENERAL_FINANCE` decline | Confirms Nova stays on-topic |
| "send 200 to david.ng" typed into the **ask** box | `TRANSFER_INTENT`, redirect-style reply | Confirms the ask endpoint doesn't try to execute it |
| Kill your network mid-`ask` for a balance question | `ASK_PROVIDER_UNAVAILABLE` shown as a real error | Confirms you didn't accidentally make this one "soft" in your UI |
| Kill your network mid-`ask` for "hello" | A friendly fallback line, no error toast | Confirms you didn't accidentally make this one "hard" in your UI |

---

## 12. Gotchas — read this before you ship

- **Never log the PIN.** It's a plain request field on
  `execute-transfer` — make sure your HTTP logging/interceptor setup
  (if you have request/response logging for debugging) redacts `pin`
  the same way it should already redact tokens.
- **`intent.amount_major` is a display string, not something to do
  math on.** It's major units (e.g. `"5000.00"`), while every amount
  elsewhere in the app is minor-unit integers. Don't mix them — use
  the `quote` object's minor-unit fields for anything computational,
  and `amount_major` only if you want to echo back exactly what the
  user typed.
- **`execute_at` is your only signal for immediate vs. scheduled** at
  the parse stage. Check `intent.execute_at != null` (or
  `parsedIntent.isScheduled` in the model above) before deciding which
  confirm-screen copy to show — "Send now" vs. "Schedule for [time]".
- **Don't treat every non-200 the same way.** `ASK_PROVIDER_UNAVAILABLE`
  should look like a real error to the user; a model-classification
  hiccup that falls back to a canned greeting should look like a normal
  reply. If your error-handling code is generic across all endpoints,
  double-check it doesn't accidentally swallow the one code that's
  supposed to be visible.
- **Treat `answer` as trusted, render-ready text** — it's plain
  natural-language prose meant to be shown directly in a bubble, not
  a structured payload you need to parse further. If you want
  structured numbers (for a card, a chart, etc.), use `data`, not
  `answer`.
- **A `TRANSFER_INTENT` reply from `/ai/ask` does not create a
  transfer.** It's just a redirect message. Don't be tempted to
  auto-forward the question to `/ai/execute-transfer` — the user typed
  it into the *question* box, and Nova's whole point here is telling
  them where the actual send flow lives, not guessing that they meant
  to commit money.