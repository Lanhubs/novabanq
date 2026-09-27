"""Scheduled-transfer scheduler.

A loop that fires scheduled transfers whose time has come. Runs
indefinitely, polling ``scheduled_service.execute_due`` every
``POLL_INTERVAL_SECONDS``.

Run:
    python -m scripts.run_scheduler

Requires:
    * A working ``.env`` with Firebase credentials (the scheduler
      talks to Firestore directly — no HTTP server involved).
    * The composite index on ``scheduled_transfers`` (``status`` ASC,
      ``execute_at`` ASC) created in Firestore. Without it, the
      ``list_due`` query fails at call time.

Design notes:
    * The loop is single-process by design for the demo, but the
      service layer is written to be safe against multiple
      schedulers running concurrently. Two schedulers both picking
      up the same due transfer dedupe at the ledger (same
      deterministic idempotency key) and one loses the
      ``mark_settled`` race with a logged CRITICAL. If the demo ever
      needs to run more than one scheduler, it can — no leader
      election is required, just accept the possibility of a
      CRITICAL log line in the rare overlap case.

    * Infrastructure failures (Firestore outage, FX provider down)
      end the current pass and the loop sleeps before retrying.
      Business rejections are recorded on the transfer itself and
      don't stop the loop.

    * **Ctrl+C semantics.** ``KeyboardInterrupt`` is delivered at the
      next bytecode check in the main thread, which is *not* only
      inside ``time.sleep()`` — it can fire at any point inside
      ``execute_due`` or ``_fire_one``. The scheduler therefore does
      not guarantee that a pass in progress completes cleanly. The
      concrete hazard is narrow: an interrupt landing inside
      ``_fire_one`` between ``execute_pre_authorized`` returning a
      settled result and ``mark_settled`` succeeding leaves the
      scheduled-transfer document ``PENDING`` even though the money
      already moved.

      Recovery from that state is *not* automatic. On the next pass,
      ``execute_pre_authorized`` finds the committed ledger
      transaction under the deterministic idempotency key and raises
      ``DuplicateTransferError`` (from the transfers repository's
      pre-check), which ``_fire_one`` records as a terminal business
      failure — the scheduled transfer ends up FAILED even though the
      money settled. **Fixing that recovery path is a known
      follow-up**: ``_fire_one`` should treat
      ``DuplicateTransferError`` as a successful settlement and mark
      the scheduled transfer SETTLED with the transaction id from
      the idempotency record, rather than FAILED.

    * The loop is intentionally simple. It doesn't do exponential
      backoff on repeated Firestore failures, doesn't expose
      metrics, and doesn't support graceful shutdown beyond Ctrl+C.
      For production, this would become a proper worker with a
      heartbeat, structured logs, and a supervisor.
"""

import logging
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.core.constants import SCHEDULED_TRANSFER_BATCH_SIZE
from app.core.exceptions import NovaBanqError
from app.features.transfers import scheduled_service

load_dotenv()

# How often the loop polls for due transfers. 30 seconds is a
# balance: tight enough that a transfer scheduled for "in 2 minutes"
# fires within a few seconds of its time (good for demos), loose
# enough that a long-running loop doesn't hammer Firestore.
POLL_INTERVAL_SECONDS = 30

# How long to sleep after an unhandled exception before trying again.
# Longer than the normal poll interval so a persistent Firestore
# outage doesn't produce a hot loop of failed queries.
ERROR_BACKOFF_SECONDS = 60

logger = logging.getLogger("scheduler")


def _one_pass() -> int:
    """Run a single scheduler pass and return how many transfers processed.

    Does not catch anything. Any exception raised by ``execute_due``
    — a Firestore outage while listing due transfers, an
    infrastructure failure while firing one — propagates to the
    caller (``main``), which logs it and backs off before retrying.
    """
    now = datetime.now(timezone.utc)
    processed = scheduled_service.execute_due(
        now=now,
        batch_size=SCHEDULED_TRANSFER_BATCH_SIZE,
    )
    return processed


def main() -> None:
    """Run the scheduler loop until interrupted.

    Catches two classes of exception per pass and sleeps before
    retrying:

        * ``NovaBanqError`` — anything the service layer raises that
          escaped ``execute_due``. Infrastructure failures (status
          >= 500) propagate up; business rejections are handled
          inside ``_fire_one`` and never reach here. Either way,
          log the specific error code and back off.
        * ``Exception`` — anything unexpected: a bug in the service,
          a Firestore SDK surprise. Log the full traceback so it's
          diagnosable, then back off and retry. A scheduler that
          silently stops is worse than one that keeps trying.
    """
    logger.info(
        "Scheduler started. Polling every %d seconds, batch size %d.",
        POLL_INTERVAL_SECONDS,
        SCHEDULED_TRANSFER_BATCH_SIZE,
    )
    try:
        while True:
            try:
                processed = _one_pass()
                if processed > 0:
                    logger.info(
                        "Processed %d scheduled transfer(s) this pass.",
                        processed,
                    )
            except NovaBanqError as exc:
                # Infrastructure failures (status >= 500) reach here;
                # business rejections are handled inside `_fire_one`
                # and don't. Log the specific error code and back off
                # before retrying.
                logger.error(
                    "Scheduler pass failed: [%s] %s. Sleeping %d "
                    "seconds before retry.",
                    exc.code.value,
                    exc.message,
                    ERROR_BACKOFF_SECONDS,
                )
                time.sleep(ERROR_BACKOFF_SECONDS)
                continue
            except Exception:  # noqa: BLE001
                # A truly unexpected error — a bug in the service, a
                # Firestore SDK surprise. Log the full traceback so
                # it's diagnosable, then back off and retry. A
                # scheduler that silently stops is worse than one
                # that keeps trying.
                logger.exception(
                    "Scheduler pass raised an unexpected error. "
                    "Sleeping %d seconds before retry.",
                    ERROR_BACKOFF_SECONDS,
                )
                time.sleep(ERROR_BACKOFF_SECONDS)
                continue

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    main()