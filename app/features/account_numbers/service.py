"""Account number service.

Generates unique NovaBanq account numbers and reserves them for users.

Account number format:
    NB + 2-digit country prefix + 8 random digits
    Example: NB0147293810 (Nigeria)

The country prefix is derived from the user's country at the time of
creation. The 8 trailing digits are random; collisions are handled by
retrying until an unused number is found.

Race-safety:
    Generation is speculative and reservation is atomic. If two
    requests generate the same candidate, only one reservation wins —
    the loser retries with a fresh candidate.
"""

import logging
import secrets

from app.core.constants import (
    ACCOUNT_NUMBER_COUNTRY_PREFIX,
    ACCOUNT_NUMBER_MAX_RETRIES,
    ACCOUNT_NUMBER_PREFIX,
    ACCOUNT_NUMBER_RANDOM_DIGITS,
    ErrorCode,
)
from app.core.exceptions import NovaBanqError
from app.features.account_numbers import repository

logger = logging.getLogger(__name__)


class AccountNumberGenerationError(NovaBanqError):
    """Raised when a unique account number cannot be generated."""

    status_code = 500
    code = ErrorCode.INTERNAL_ERROR
    message = "Could not generate a unique account number. Please try again."


def _build_candidate(country_code: str) -> str:
    """Construct a single account number candidate.

    Uses ``secrets.randbelow`` rather than ``random`` so that generated
    numbers are not predictable from previously issued numbers. This
    matters because account numbers are shared publicly and a guessable
    sequence is a privacy and enumeration risk.
    """
    prefix = ACCOUNT_NUMBER_COUNTRY_PREFIX.get(country_code)
    if prefix is None:
        raise AccountNumberGenerationError(
            f"Unsupported country code '{country_code}' for account number "
            "generation."
        )

    upper_bound = 10 ** ACCOUNT_NUMBER_RANDOM_DIGITS
    random_part = secrets.randbelow(upper_bound)
    random_str = str(random_part).zfill(ACCOUNT_NUMBER_RANDOM_DIGITS)

    return f"{ACCOUNT_NUMBER_PREFIX}{prefix}{random_str}"


def generate_and_reserve(uid: str, country_code: str) -> str:
    """Generate a unique account number and reserve it for the given uid.

    Retries up to ``ACCOUNT_NUMBER_MAX_RETRIES`` times if the candidate
    is already taken. Collisions are astronomically rare (100 million
    combinations per country prefix), but the atomic reservation makes
    the retry loop correct under concurrency.

    Args:
        uid: The Firebase uid of the user who will own the number.
        country_code: Two-letter ISO country code (e.g. "NG", "GH").

    Returns:
        The generated account number.

    Raises:
        AccountNumberGenerationError: If no unique number could be
            generated after the maximum number of attempts.
    """
    for attempt in range(1, ACCOUNT_NUMBER_MAX_RETRIES + 1):
        candidate = _build_candidate(country_code)

        if repository.reserve_atomic(candidate, uid):
            return candidate

        logger.warning(
            "Account number collision on attempt %d/%d for uid=%s.",
            attempt,
            ACCOUNT_NUMBER_MAX_RETRIES,
            uid,
        )

    logger.error(
        "Exhausted %d attempts to generate a unique account number for uid=%s "
        "in country=%s.",
        ACCOUNT_NUMBER_MAX_RETRIES,
        uid,
        country_code,
    )
    raise AccountNumberGenerationError()