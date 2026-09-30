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
**NovaBanq — send money across Africa in seconds. No markup. No multi-app dance.**

---

### Try it right now — 30 seconds, no install

📱 **[Launch the live app in your browser](https://appetize.io/app/b_2xkrdxr27mcqlv5gy2iyj7ix3e?device=pixel7&osVersion=13.0&toolbar=true)** — the real Flutter app, streaming to your browser. No download, no Play Store, no phone required. Sign in and start sending transfers in under 30 seconds.

🎬 **[Watch the 3-minute walkthrough](PASTE_YOUR_VIDEO_URL_HERE)** — if you'd rather see it end to end first.

**Demo login:**
- Email: `code5withkakes@gmail.com`
- Password: `david12345`

Sign in once and you land on the dashboard — the account is pre-seeded with a funded balance, so you can go straight to sending a transfer or asking Nova a question.

---

### The problem we built NovaBanq for

Sub-Saharan Africa is the **most expensive region on Earth** to send money to — **8.46% average fees**, against a **6.36% global average**. The World Bank's own data identifies the **Ghana → Nigeria corridor** as one of only **twenty routes worldwide** where **no service at all** meets its standard for a fast, transparent, reasonably priced transfer.

Every app that tries to fix this hands the user the mess anyway:

1. Open the app
2. Pick a currency
3. Compare exchange rates
4. Do the FX math manually
5. Fill in the recipient's bank details
6. Confirm — and hope the fee you saw is the fee you pay

That's the flow the 8.46% figure comes from. It's a form disguised as a product. The complexity is the tax.

---

### What NovaBanq does differently

**One account. One currency. One @tag.** Every user has a single account in their own country's currency, plus a tag like `@david.ng`. When a Ghanaian sends cedis to a Nigerian's `.ng` tag, the FX conversion happens **invisibly inside the transfer**. The sender sees cedis leave. The recipient sees naira arrive. Nobody opens a currency picker. Nobody compares rates. Nobody does the math.

**And the send form doesn't exist.** The user types:

> *"send 500 cedis to david.ng"*

And Nova — our AI assistant — parses the sentence, prices it live against the real GHS→NGN corridor, and reads back exactly what's about to happen: the recipient's name, the amount, the fee, and what David will actually receive in his own currency. One sentence. One PIN. The money is on its way.

**The PIN never touches the language model.** The AI proposes; the user authorizes. Every decision the old flow asked the user to make — currency, rate, recipient, fee — the AI already made. What's left is a single tap.

This is not a chatbot bolted onto a payments app. It's the interface that makes cross-border sending feel like sending money to the person next to you.

---

### Why it matters for Africa

The 8.46% isn't an abstraction. It's what a Ghanaian nurse pays to send money home to her mother in Lagos. It's what a Nigerian freelancer loses every time a client in Accra pays him. It's what a Senegalese shop owner pays to receive CFA from a cousin in Abidjan. Every percentage point is a meal, a school fee, a phone credit, a doctor's visit — taken by rails that route through London.

NovaBanq is a closed-loop ledger for app-to-app transfers, with a thin adapter over Flutterwave and Paystack for money in and money out. Once money is inside NovaBanq, moving it between users costs the platform almost nothing. That's why the fee is **1% flat** — a fraction of what intra-African rails cost today. The savings go to the people sending money to their families, not to intermediaries in another hemisphere.

---

### Try the AI in the browser

If you want to see the AI alone without the mobile app shell:

- **API reference:** the endpoints below are all live and authenticated with a Firebase ID token
- **Full flow:** `/api/v1/ai/ask` takes a plain-language question and returns either an answer grounded in the user's own ledger, or a structured transfer confirmation ready to be executed
- **Execute:** `/api/v1/ai/execute-transfer` takes the confirmed intent plus a PIN and settles the transfer against the double-entry ledger

Every endpoint is documented below. Every error is structured. Every transfer is idempotent.

---

### Built by

- **Daniel Clement Toluwalase** — Founder and UI/UX Designer
- **Kakes David** — Software Engineer, Backend Engineer, and CTO
- **Habeeb Mohammed Olanrewaju** — Frontend Developer

---

**Sign in with the demo account above and send your first cross-border transfer in under 30 seconds.**
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