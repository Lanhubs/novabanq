"""Account service.

Business logic for the accounts feature. Reads the user's account and,
on first access, creates it with a zero balance in the user's own
currency.

This layer contains no HTTP and no direct Firestore calls. It
orchestrates the account repository and the users service.

The accounts API is read-only from the client's perspective. There is
no create endpoint — the account materialises the first time the user
reads their balance. This keeps the onboarding flow short and means the
frontend never has to coordinate account creation.
"""

import logging
from typing import Any

from app.core.constants import ErrorCode
from app.core.exceptions import NovaBanqError
from app.features.accounts import repository
from app.features.accounts.schemas import AccountResponse, build_account_response
from app.features.users import service as users_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class AccountUnavailableError(NovaBanqError):
    """Raised when the account cannot be read or created.

    Wraps Firestore failures into a single retryable outcome. The
    client never sees which subsystem failed.
    """

    status_code = 502
    code = ErrorCode.INTERNAL_ERROR
    message = "Account service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_create_for_user(uid: str) -> AccountResponse:
    """Return the authenticated user's account, creating it if needed.

    On first access the account is created with a zero balance in the
    currency from the user's profile. On subsequent calls the existing
    account is returned unchanged.

    Args:
        uid: Firebase uid of the caller.

    Returns:
        The user's account, serialized for the API.

    Raises:
        UserNotFoundError: If no profile exists for this uid. Raised by
            ``users_service.get_profile`` and left unhandled here so it
            propagates as-is.
        AccountUnavailableError: On any Firestore failure.
    """
    # 1. Load the profile — this confirms a profile exists and gives us
    #    the currency. It does not confirm the user has finished
    #    onboarding: currency is set when the profile is created, before
    #    the tag, PIN, and identity verification steps.
    profile = users_service.get_profile(uid)
    currency = profile.get("currency")

    if not currency:
        # A profile without a currency is a data integrity bug — the
        # users service always sets one at creation.
        logger.error(
            "Profile for uid=%s has no currency; cannot create account.", uid
        )
        raise AccountUnavailableError()

    # 2. Read or create the account.
    try:
        account = repository.get_or_create(uid, currency)
    except repository.AccountRepositoryError as exc:
        raise AccountUnavailableError() from exc

    # 3. Project to the response shape. A malformed stored document
    #    would raise ValueError here, which is also an outage from the
    #    caller's perspective — retrying won't help, but it's not the
    #    client's fault either.
    try:
        return build_account_response(account)
    except ValueError as exc:
        logger.exception(
            "Malformed account document for uid=%s; cannot build response.",
            uid,
        )
        raise AccountUnavailableError() from exc


def get_balance_minor(uid: str) -> int:
    """Return the user's current balance in the smallest currency unit.

    Used by other services (funding, transfers) that need to check a
    balance before performing an operation. A user with no account yet
    has a balance of zero, so a missing account is not an error.

    Args:
        uid: Firebase uid of the caller.

    Returns:
        The current balance, or 0 if the account does not exist.

    Raises:
        AccountUnavailableError: On any Firestore failure.
    """
    try:
        account = repository.get(uid)
    except repository.AccountRepositoryError as exc:
        raise AccountUnavailableError() from exc

    if account is None:
        return 0

    balance = account.get("balance_minor", 0)
    return int(balance)