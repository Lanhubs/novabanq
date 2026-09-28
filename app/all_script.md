# Scripts Reference

Full command reference for every script in `scripts/`.

---

## Table of Contents

- [Seeding](#seeding)
- [Testing / Smoke Tests](#testing--smoke-tests)
- [Scheduler](#scheduler)
- [Inspector (unofficial)](#inspector-unofficial--used-ad-hoc-during-this-session)
- [Dependency Matrix](#dependency-matrix)
- [Scripts Most Likely to Break](#scripts-most-likely-to-break)
- [End-to-End Demo Sequence](#end-to-end-demo-sequence)

---

## Seeding

### Seed the demo users

Creates two funded users in Firebase + Firestore. Idempotent — safe to re-run.

```powershell
python -m scripts.seed_demo_users
```

### Seed the FX corridors

Populates all 20 directed currency pairs from FxRatesAPI. Idempotent unless `--force` is passed.

```powershell
python -m scripts.seed_corridors
```

### Fund a specific user's account via the ledger

Takes an email and an amount in major units.

```powershell
python -m scripts.fund_user <email> <amount_major_units>
```

**Example:**

```powershell
python -m scripts.fund_user codewithkakes@gmail.com 5000
```

---

## Testing / Smoke Tests

> All scripts in this section require **uvicorn** to be running.

### Transactions endpoints smoke test

Hits `/transactions` and `/transactions/{id}` as sender, recipient, and outsider.

```powershell
python -m scripts.test_transactions_endpoints
```

### Funding endpoints smoke test

Creates a virtual account and fires a mock webhook.

```powershell
python -m scripts.test_funding
```

### Scheduled-transfer endpoints smoke test

Schedules a transfer 2 minutes out and polls for the terminal state.
Requires uvicorn **and** the scheduler (either as a separate process, or via the in-process worker that starts with uvicorn).

```powershell
python -m scripts.test_scheduled
```

### AI intent smoke test

Fires four natural-language phrasings at `/ai/parse-transfer`.

```powershell
python -m scripts.test_ai_intent
```

### AI execute-transfer smoke test

Fires four phrasings at `/ai/execute-transfer` with a real PIN and a real transfer.

```powershell
python -m scripts.test_ai_execute
```

### Nova interactive chat

Signs in as the demo sender and lets you type questions one at a time. Type `exit` or `quit` to stop.

```powershell
python -m scripts.ask_nova
```

---

## Scheduler

### Run the scheduled-transfer worker as a standalone process

Only needed if the in-process scheduler (which starts automatically with uvicorn) is disabled, or for local debugging.

```powershell
python -m scripts.run_scheduler
```

---

## Inspector (unofficial — used ad-hoc during this session)

> These aren't officially delivered files — they were given as inline `python -c` snippets. The commands below only work if you saved them to the paths shown.

### Dump the first few transaction documents

If saved as `scripts/dump_transactions.py`:

```powershell
python -m scripts.dump_transactions
```

### Dump scheduled-transfer documents

If saved as `scripts/dump_scheduled.py`:

```powershell
python -m scripts.dump_scheduled
```

---

## Dependency Matrix

What each script needs running alongside it.

| Script | Needs uvicorn? | Needs scheduler? |
|---|:---:|:---:|
| `seed_demo_users` | No | No |
| `seed_corridors` | No | No |
| `fund_user` | No | No |
| `test_transactions_endpoints` | **Yes** | No |
| `test_funding` | **Yes** | No |
| `test_scheduled` | **Yes** | **Yes** *(in-process or standalone)* |
| `test_ai_intent` | **Yes** | No |
| `test_ai_execute` | **Yes** | No *(unless testing scheduled path)* |
| `ask_nova` | **Yes** | No |
| `run_scheduler` | No | N/A — *is* the scheduler |

---

## Scripts Most Likely to Break

1. **`ask_nova` and `test_ai_execute`** — fail if `GEMINI_API_KEY` is unset or the model name is stale. Both hit Gemini directly through the running server. A `502` or `500` mentioning "Gemini" means check `.env` first.

2. **`test_scheduled`** — requires the scheduler to actually be running. Since the scheduler now runs in-process, uvicorn starting it means `test_scheduled` works with only uvicorn up — but the fire window is 5 minutes, so a transfer scheduled "2 minutes out" must be created while uvicorn is warm. Don't schedule one and let the server spin down.

3. **`seed_corridors`** — hits FxRatesAPI twenty times in a row. If your connection drops or FxRatesAPI rate-limits you, it fails partway and leaves some corridors unpopulated. Just re-run it — it skips existing corridors unless `--force` is passed.

---

## End-to-End Demo Sequence

There's no single script that runs seed → fund → test as one chain, but this is the order that makes sense — seed first, then exercise each endpoint group:

```powershell
python -m scripts.seed_demo_users
python -m scripts.seed_corridors
python -m scripts.test_transactions_endpoints
python -m scripts.test_funding
python -m scripts.test_ai_execute
python -m scripts.ask_nova
```

> Run this with **uvicorn already running** in a separate terminal.