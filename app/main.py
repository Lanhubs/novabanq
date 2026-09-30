"""NovaBanq API application entry point.

Builds the FastAPI application, wires middleware, registers exception
handlers, and mounts the versioned API router.

Background scheduler:
    A single APScheduler ``BackgroundScheduler`` runs inside this
    process and fires due scheduled transfers every 30 seconds. The
    scheduler job calls ``scheduled_service.execute_due``, the same
    function ``scripts/run_scheduler.py`` calls — that script remains
    for local testing and debugging, but is redundant in any
    deployment that runs the API (this process).

    The scheduler runs in a background thread of the same process as
    uvicorn. It does not need a second terminal or a separate Render
    service. This is deliberate: the scheduler is a part of the API
    process because that is where the ledger, the accounts service,
    and the notifications service already live, and the callback
    reuses them directly.

    Restart safety: if uvicorn restarts while a scheduled transfer is
    mid-execution, the ``execute_due`` call is lost. The next pass
    after restart re-runs the same transfer; the ledger's deterministic
    idempotency key (derived from the scheduled_transfer_id) dedupes
    the second attempt, and ``_fire_one``'s DuplicateTransferError
    recovery marks the scheduled transfer SETTLED using the
    transaction id from the ledger's idempotency record. So a restart
    cannot double-settle a transfer, and cannot leave one stranded in
    PENDING after the money has moved.

    Multi-worker safety: if uvicorn is ever run with ``--workers N``,
    each worker will start its own scheduler instance, and they will
    all poll Firestore. Two schedulers firing the same due transfer
    dedupe at the ledger (same deterministic key) and one loses the
    ``mark_settled`` race with a logged CRITICAL. No double-spend —
    just a loud log line. For the demo, run a single worker.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.constants import SCHEDULED_TRANSFER_BATCH_SIZE
from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import NovaBanqError
from app.features.transfers import scheduled_service
from app.infra.firebase.client import get_firebase_app


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# httpx logs the full URL of every outbound request at INFO level —
# including any query parameters. Vendors that accept API keys as a
# query string (rather than a header) would leak those keys into this
# log, and every log shipper that collects it. We send our FX vendor's
# key in a header specifically to keep it out of the URL, but silencing
# httpx's INFO chatter here is defense in depth: if a future client
# ever puts a secret in a query param, it still won't reach the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# How often the in-process scheduler polls for due transfers. Matches
# ``scripts/run_scheduler.POLL_INTERVAL_SECONDS`` so the script and
# the in-process scheduler behave identically when both are running.
_SCHEDULER_INTERVAL_SECONDS = 30


def _run_scheduler_pass() -> None:
    """One scheduler pass, wrapped for the background scheduler.

    Called by APScheduler on its own thread. Catches every exception
    so a single failed pass cannot kill the scheduler thread — an
    uncaught exception inside an APScheduler job is logged by the
    library but the job's next invocation still runs. This wrapper
    makes the log specific to the scheduler and keeps the failure
    handling in one place.

    The exact same logic as ``scripts/run_scheduler._one_pass`` plus
    the same error handling ``scripts/run_scheduler.main`` applies in
    its loop. Duplicated rather than imported because the script is a
    CLI tool with its own logging and its own lifecycle; pulling that
    into an importable form to save eight lines would couple the
    server process to a script.
    """
    try:
        processed = scheduled_service.execute_due(
            batch_size=SCHEDULED_TRANSFER_BATCH_SIZE,
        )
        if processed > 0:
            logger.info(
                "Scheduler pass processed %d scheduled transfer(s).",
                processed,
            )
    except NovaBanqError as exc:
        # Infrastructure failure — Firestore unreachable, FX provider
        # down. Log the specific error code and move on; the next
        # 30-second tick retries.
        logger.error(
            "Scheduler pass failed: [%s] %s.",
            exc.code.value,
            exc.message,
        )
    except Exception:  # noqa: BLE001
        # A truly unexpected error — a bug, an SDK surprise. Log the
        # full traceback so it's diagnosable, then let the next tick
        # try again. A scheduler thread that dies silently is worse
        # than one that keeps failing loudly.
        logger.exception("Scheduler pass raised an unexpected error.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs on startup and shutdown."""
    logger.info(
        "Starting %s v%s (env=%s, demo_mode=%s).",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.demo_mode,
    )
    firebase_app = get_firebase_app()
    logger.info("Firebase project connected: %s", firebase_app.project_id)

    # Start the in-process scheduler. Runs ``_run_scheduler_pass`` on
    # an interval in a background thread. ``replace_existing=True``
    # makes startup idempotent if the lifespan ever fires twice in a
    # single process (it shouldn't, but the argument is cheap).
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_scheduler_pass,
        trigger="interval",
        seconds=_SCHEDULER_INTERVAL_SECONDS,
        id="scheduled_transfer_pass",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduled-transfer worker started (interval=%ds).",
        _SCHEDULER_INTERVAL_SECONDS,
    )

    yield

    # Shut the scheduler down before the process exits. ``wait=False``
    # means we don't block on a pass that's mid-execution — the
    # DuplicateTransferError recovery path handles a settled-but-
    # unmarked transfer on the next startup, so an abrupt stop here is
    # safe.
    scheduler.shutdown(wait=False)
    logger.info("Scheduled-transfer worker stopped.")
    logger.info("Shutting down %s.", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="""
# NovaBanq — send money across Africa in seconds. No markup. No multi-app dance. No currency picker.

**Try it live in your browser right now — 30 seconds, no install, no phone required.**

---

## 🚀 Launch the live app

📱 **[Primary demo link — launch the Flutter app in your browser](https://appetize.io/app/b_2xkrdxr27mcqlv5gy2iyj7ix3e?device=pixel7&osVersion=13.0&toolbar=true)**

🔁 **[Backup demo link — use this if the primary is exhausted](https://appetize.io/app/b_vo77v2vpnudkp22cu57ld4vkya)**

📂 **[Source code — browse the full repo on GitHub](https://github.com/Lanhubs/novabanq)**

The demo links stream the real Flutter app to your browser — no download, no Play Store, no install. In under 30 seconds you'll be signed in and sending a cross-border transfer. The repository above is the actual code behind everything you're about to see — every claim below is something you can go read for yourself.

---

## 🔑 Demo account — sign in and start sending

**Ghana account (sender, funded, ready to send):**
- Email: `codewithkakes@gmail.com`
- Password: `test1234`
- Transaction PIN: `48392` (needed to confirm any transfer)

Once signed in, you land directly on the dashboard — the account is pre-seeded with a funded balance, so you can go straight to the send flow or ask Nova a question.

**Who you can send to — two live Nigerian recipients:**

- **`david.ng`** — a real Nigerian account on the platform
- **`olanrewaju.ng`** — a real Nigerian account on the platform

Try this in the AI chat: type **"send 500 cedis to david.ng"** and watch Nova parse the sentence, price the GHS→NGN corridor live, and read back exactly what's about to happen — before any money moves. Enter the PIN (`48392`), and a real 5-leg ledger transaction settles in the background.

---

## ⚡ In the next 30 seconds, you'll watch

- A sentence — not a form — become a fully-priced, ready-to-execute cross-border transfer
- Two different currencies bridge invisibly inside one transfer, with no currency picker anywhere in the flow
- A real double-entry ledger settle a 5-leg atomic transaction against a live FX rate
- An AI that's allowed to *propose* a transfer, and is never, ever allowed to *move money* on its own

That last point is the whole engineering story of this project. Everything below explains why it's harder than it sounds, and why almost nobody has shipped it.

---

## 🌍 The problem we built NovaBanq for

**Sub-Saharan Africa isn't a one-off outlier — it's held the title of the world's most expensive region for remittances for more than fifteen years running,** according to the World Bank's own Remittance Prices Worldwide data.

- **8.46% average fees** across the region, against a **6.36% global average**
- The World Bank tracks roughly twenty corridors worldwide where *no service at all* meets its own bar for a fast, transparent, reasonably priced transfer — the **Ghana → Nigeria corridor is one of them**

**Why the costs are so high:** intra-African payment corridors route through Europe or the US. Lagos to Accra goes Lagos → London → Accra. Lagos to London goes Lagos → London. The intra-African route is longer and more expensive because the rails don't exist yet. Every percentage point those rails cost is a meal, a school fee, a doctor's visit, a phone credit — taken by intermediaries in another hemisphere who never touch the money for more than a few milliseconds.

**And what does every app that tries to fix this do?** It hands the user the mess anyway:

1. Open the app
2. Pick a currency you're sending in
3. Pick a currency they'll receive
4. Compare exchange rates against a market you don't know
5. Do the FX math manually
6. Fill in a recipient's bank details
7. Confirm — and hope the fee you saw is the fee you pay

The complexity is the tax. The form *is* the product. That's the 8.46%.

---

## 💡 What NovaBanq does that no other fintech application in the world does

### 1. One account. One currency. Invisible FX inside the transfer.

Every other cross-border app asks the user to hold multiple currencies, or to pick a currency on the send screen, or to see a rate and confirm the conversion. **We don't.** Every NovaBanq user has a **single account in their own country's currency**, plus a **@tag** with a country suffix like `@david.ng`.

When a Ghanaian sends cedis to a Nigerian's `.ng` tag, the FX conversion happens **invisibly inside the transfer**. The sender sees cedis leave. The recipient sees naira arrive. Neither opens a currency picker. Neither compares rates. Neither does the math. **Nobody in the world has shipped this combination as a product.**

### 2. The send form doesn't exist — AI is the interface.

Every other app in this category is a form. **NovaBanq's is a conversation.** The user types:

> *"send 500 cedis to david.ng"*

And Nova — our AI layer — parses the sentence, prices it live against the real GHS→NGN corridor, and reads back exactly what's about to happen: the recipient's name, the amount, the fee, and what David will actually receive in his own currency. One sentence. One PIN. The money is on its way.

**The PIN never touches the language model.** The AI proposes; the user authorizes. Every decision the old flow asked the user to make — currency, rate, recipient, fee — the AI already made. What's left is a single tap.

**This is not a chatbot bolted onto a payments app.** It's an AI that knows your ledger, prices the transfer, and executes it against a real double-entry system when you say so. No fintech application anywhere — Africa, Europe, the US — ships this combination today.

### 3. A double-entry ledger underneath, built for correctness.

The AI is the interface. Underneath it is a real ledger, engineered the way a bank's ledger has to be, not the way a demo's ledger can get away with being:

- **5-leg atomic transactions** for cross-currency transfers — every leg commits together or none of them do, so a crash mid-transfer can never leave money half-moved
- **Idempotency keys enforced inside the Firestore transaction itself** — the same request retried a hundred times over a bad connection still only moves money once
- **Deterministic replay** for scheduled transfers, so a server restart mid-execution re-runs safely instead of double-sending or losing the transfer
- **bcrypt-hashed PINs with lockout** on repeated failed attempts
- **Transactional status preconditions**, so a scheduler race or a badly-timed cancel can never leave a transfer in a state that isn't fully settled or fully reverted

The AI is fast and friendly; the ledger is slow, careful, and correct. **The AI never has the authority to move money — it only proposes what should move.** That sentence is enforced in code, not just in a system prompt — read the ledger and transfers modules in [the repo](https://github.com/Lanhubs/novabanq) and you'll see it for yourself.

---

## 🛠️ Who built NovaBanq

**Daniel Clement Toluwalase — Founder and UI/UX Designer**
Daniel designed the entire NovaBanq experience: the flow, the interface, and the visual identity of the product. Every screen in the live demo — from the dashboard to the transfer confirmation — was designed by him. He's one of the original founders and the reason NovaBanq feels like a product instead of a prototype.

**Kakes David — Software Engineer, Backend Engineer, and CTO**
Kakes built and maintains the entire backend: the double-entry ledger, the transfers engine, the FX corridor cache, the AI intent parser, the AI assistant Nova, the scheduled-transfer worker, and every API endpoint you're looking at on this page. He architected the system around a simple rule — **the AI proposes, the ledger decides** — and built the ledger so that rule is enforced in code, not just in the prompt. [**See it yourself in the repo.**](https://github.com/Lanhubs/novabanq)

**Habeeb Mohammed Olanrewaju — Frontend Developer**
Habeeb built the Flutter app that streams to your browser via the Appetize link above. Every screen you tap, every form you fill, every animation you see was written by him. He's the reason the app doesn't just work — it feels fast, smooth, and finished.

---

## 🔬 Try the AI directly, without the app shell

If you want to see the AI layer on its own, every endpoint below is live, authenticated, and documented. The two that matter most:

**`POST /api/v1/ai/ask`** — takes a plain-language question and returns an answer grounded in the user's own ledger. Try: *"what's my balance"*, *"who did I send to last"*, *"did my scheduled transfer go out"*. Or type a transfer command and get back a structured confirmation ready to execute.

**`POST /api/v1/ai/execute-transfer`** — takes the confirmed intent plus a PIN and settles the transfer against the ledger. Idempotent. Verified recipient. Verified PIN. Either it settles, or it returns a specific, user-facing error.

Every endpoint is documented below with example requests, example responses, and every error code.

---

**Sign in with the demo account above and send your first cross-border transfer in under 30 seconds. Or open the [repository](https://github.com/Lanhubs/novabanq) and read the ledger code that makes it safe to do so.**

**Built by Daniel, Kakes, and Habeeb. For Africa.**
""",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness probe. Returns app status and current environment."""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "demo_mode": settings.demo_mode,
        },
        "error": None,
    }