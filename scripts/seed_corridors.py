"""Seed script: populate the ``corridors`` collection.

Run this once to create every directed corridor between the supported
currencies, with a live rate from FxRatesAPI. After this has run, the
runtime path in ``app/features/currency/service.py`` keeps the rates
fresh automatically — this script is only for the initial population,
for recovery if the collection is ever cleared, and for adding a new
currency to the supported set.

Usage:

    python -m scripts.seed_corridors
    python -m scripts.seed_corridors --force   # re-fetch every corridor
    python -m scripts.seed_corridors --dry-run # print what would be done

Behavior:

    * Iterates every ordered pair of supported currencies (5
      currencies → 20 directed pairs).
    * Skips pairs that already have a corridor unless ``--force`` is
      passed. This makes re-runs cheap and non-destructive: a normal
      run after the first does nothing, which is the right default for
      a seed script invoked casually.
    * Fetches one live rate per corridor from FxRatesAPI via
      ``service.refresh_corridor``. That function preserves any
      existing ``fee_bps`` on the corridor, so an operator-tuned fee
      is never overwritten by a reseed.
    * Sleeps between calls to stay well inside the FxRatesAPI free
      tier's per-minute budget. 20 calls at 2 s apart is 40 s of wall
      time — comfortably under any per-minute limit the free tier
      enforces.
    * Fails per-corridor, not globally. A single provider hiccup on
      one pair does not abort the other nineteen; the summary at the
      end names exactly which pairs failed.

This module does not import the FastAPI app. It talks to Firestore and
FxRatesAPI through the same service the running app uses, but it runs
as a standalone script so it can be invoked without a server.
"""

import argparse
import logging
import sys
import time

from app.core.constants import Currency
from app.features.currency import repository, service
from app.infra.fx.schemas import FxRatesClientError

logger = logging.getLogger(__name__)

# Minimum spacing between outbound FxRatesAPI calls. The free tier
# allows a burst but the seed script's 20 calls are one-time, so being
# conservative here costs nothing and avoids ever tripping the limit.
_REQUEST_SPACING_SECONDS = 2.0


def _supported_currencies() -> list[Currency]:
    """Return the currencies this script seeds corridors for.

    Sourced from the ``Currency`` enum so adding a currency to the
    codebase automatically adds it to the seed set. The enum is the
    single source of truth for what NovaBanq supports.
    """
    return list(Currency)


def _directed_pairs(
    currencies: list[Currency],
) -> list[tuple[Currency, Currency]]:
    """Return every ordered (from, to) pair where from != to.

    5 currencies → 20 pairs. Ordered, because ``GHS_NGN`` and ``NGN_GHS``
    are different corridor documents with different rates.
    """
    return [
        (frm, to)
        for frm in currencies
        for to in currencies
        if frm is not to
    ]


def seed(*, force: bool, dry_run: bool) -> int:
    """Populate corridors. Returns a process exit code.

    Args:
        force: If True, re-fetch and overwrite corridors that already
            exist. If False, skip existing corridors — a bare re-run
            becomes a no-op.
        dry_run: If True, print what would be done without writing to
            Firestore or calling FxRatesAPI.

    Returns:
        0 if every requested corridor was created or skipped
        successfully, 1 if any corridor failed.
    """
    currencies = _supported_currencies()
    pairs = _directed_pairs(currencies)

    print(f"Supported currencies: {', '.join(c.value for c in currencies)}")
    print(f"Directed pairs to process: {len(pairs)}")
    print()

    created = 0
    skipped = 0
    failed: list[tuple[Currency, Currency, str]] = []

    for index, (frm, to) in enumerate(pairs, start=1):
        pair_label = f"{frm.value}/{to.value}"

        if not force:
            try:
                already_exists = repository.exists(frm, to)
            except repository.CorridorRepositoryError as exc:
                message = f"existence check failed: {exc}"
                print(f"[{index:02d}/{len(pairs)}] {pair_label}: SKIP ({message})")
                failed.append((frm, to, message))
                continue

            if already_exists:
                print(f"[{index:02d}/{len(pairs)}] {pair_label}: exists, skipping")
                skipped += 1
                continue

        if dry_run:
            print(f"[{index:02d}/{len(pairs)}] {pair_label}: would fetch and write")
            continue

        try:
            rate = service.refresh_corridor(frm, to)
        except FxRatesClientError as exc:
            message = f"provider error: {exc}"
            print(f"[{index:02d}/{len(pairs)}] {pair_label}: FAILED ({message})")
            logger.warning("Corridor %s failed: %s", pair_label, exc)
            failed.append((frm, to, message))
            continue
        except repository.CorridorRepositoryError as exc:
            message = f"storage error: {exc}"
            print(f"[{index:02d}/{len(pairs)}] {pair_label}: FAILED ({message})")
            logger.warning("Corridor %s failed to persist: %s", pair_label, exc)
            failed.append((frm, to, message))
            continue

        print(
            f"[{index:02d}/{len(pairs)}] {pair_label}: "
            f"rate={rate.rate} source={rate.source.value}"
        )
        created += 1

        # Space out requests. Skip the sleep after the last call —
        # no reason to wait for nothing.
        if index < len(pairs):
            time.sleep(_REQUEST_SPACING_SECONDS)

    print()
    print("─── Summary ───")
    print(f"Created:  {created}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {len(failed)}")

    if failed:
        print()
        print("Failed pairs:")
        for frm, to, reason in failed:
            print(f"  - {frm.value}/{to.value}: {reason}")
        return 1

    return 0


def _configure_logging() -> None:
    """Emit INFO-level logs so per-corridor refreshes are visible.

    Silences httpx's per-request INFO lines. Those log every outbound
    URL, which — while our API key is now sent in a header rather than
    a query parameter — is still too noisy for a script whose whole
    point is a readable per-corridor progress report. ``main.py`` does
    the same silencing for the running app; this duplicate keeps the
    seed script's output consistent with the server's.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the corridors collection with live FX rates.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Re-fetch and overwrite corridors that already exist. "
            "Without this flag, existing corridors are left untouched."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print what would be done without calling FxRatesAPI or "
            "writing to Firestore."
        ),
    )
    args = parser.parse_args()

    _configure_logging()
    return seed(force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())