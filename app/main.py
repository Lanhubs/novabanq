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