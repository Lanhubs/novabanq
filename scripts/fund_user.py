"""Fund a user's account through the ledger.

Takes an email and an amount, looks up the user's profile, and credits
their balance by the amount. Does not touch profiles, tags, PINs, or
anything else. Sends a funding-received email to the user afterward,
matching the notification the webhook path fires.

Design decisions:
    * The amount is parsed as ``Decimal``, never ``float``. A command
      line argument like ``"19.99"`` is an exact decimal; routing it
      through ``float()`` first would introduce binary imprecision
      before it ever reaches the ledger, the same failure mode the FX
      client and corridor repository both avoid deliberately. Minor
      units are derived from the ``Decimal`` amount directly.
    * If the amount carries more precision than the currency's minor
      unit supports (e.g. three decimal places for a two-decimal
      currency), the script refuses to guess and exits with an error
      rather than silently truncating a fraction of a cent.
    * The email is best-effort, same as every other notification in
      this codebase: ``notifications_service.send_funding_received``
      swallows its own delivery failures, so a Brevo outage cannot
      turn a successful credit into an error here.

Run:
    python -m scripts.fund_user <email> <amount_major_units>
"""

import sys
import uuid

from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth

from app.core.constants import (
    CURRENCY_MINOR_UNITS,
    AccountType,
    Currency,
    EntryDirection,
    SystemAccountPurpose,
    TransactionType,
    system_account_id,
)
from app.features.accounts import service as accounts_service
from app.features.ledger import service as ledger_service
from app.features.ledger.schemas import LedgerInstruction, LedgerRequest
from app.features.notifications import service as notifications_service
from app.features.users import service as users_service
from app.infra.firebase.client import get_firebase_app

load_dotenv()


def _uid_for_email(email: str) -> str:
    """Resolve an email to a Firebase uid.

    Raises:
        firebase_auth.UserNotFoundError: If no Firebase user is
            registered with this email.
    """
    get_firebase_app()  # ensures Firebase is initialized
    user = firebase_auth.get_user_by_email(email)
    return user.uid


def _amount_to_minor(amount_major: Decimal, currency: Currency) -> int:
    """Convert a major-unit ``Decimal`` amount to an integer minor-unit amount.

    Raises:
        SystemExit: If the amount is not positive, or carries more
            precision than the currency's minor unit supports.
    """
    if amount_major <= 0:
        raise SystemExit(f"Amount must be positive, got {amount_major}.")

    scale = CURRENCY_MINOR_UNITS[currency]
    exact_minor = amount_major * scale
    amount_minor = int(exact_minor)

    if exact_minor != amount_minor:
        raise SystemExit(
            f"{amount_major} has more precision than {currency.value} "
            f"supports ({scale} minor units per major unit)."
        )

    return amount_minor


def _fund(email: str, amount_major: Decimal) -> None:
    """Credit ``email``'s ledger balance by ``amount_major``.

    Args:
        email: The recipient's Firebase-registered email address.
        amount_major: The amount to credit, in the recipient's
            currency's major units (e.g. ``Decimal("19.99")`` for
            $19.99).

    Raises:
        SystemExit: If the email has no Firebase user, the profile's
            currency is unsupported, or the amount is invalid (see
            ``_amount_to_minor``).
    """
    try:
        uid = _uid_for_email(email)
    except firebase_auth.UserNotFoundError as exc:
        raise SystemExit(f"No Firebase user found for {email!r}.") from exc

    profile = users_service.get_profile(uid)
    try:
        currency = Currency(profile["currency"])
    except (KeyError, ValueError) as exc:
        raise SystemExit(
            f"User {email!r} has no supported currency configured."
        ) from exc

    amount_minor = _amount_to_minor(amount_major, currency)

    accounts_service.get_or_create_for_user(uid)

    funding_account = system_account_id(
        SystemAccountPurpose.FX_BRIDGE, currency
    )

    debit_funding = LedgerInstruction(
        account_id=funding_account,
        account_type=AccountType.SYSTEM,
        currency=currency,
        direction=EntryDirection.DEBIT,
        amount_minor=amount_minor,
    )
    credit_user = LedgerInstruction(
        account_id=uid,
        account_type=AccountType.USER,
        currency=currency,
        direction=EntryDirection.CREDIT,
        amount_minor=amount_minor,
    )

    request = LedgerRequest(
        transaction_id=str(uuid.uuid4()),
        idempotency_key=f"manual-fund-{uuid.uuid4().hex}",
        transaction_type=TransactionType.FUNDING,
        instructions=(debit_funding, credit_user),
        metadata={
            "recipient_uid": uid,
            "to_currency": currency.value,
            "to_amount_minor": amount_minor,
            "fee_minor": 0,
        },
    )

    result = ledger_service.debit_and_credit(request)
    new_balance = accounts_service.get_balance_minor(uid)

    # Notify the user by email, same as the webhook path does. The
    # notification service swallows its own delivery failures, so a
    # Brevo outage cannot turn a successful credit into an error here.
    # Fires after the ledger commits so the email never claims a
    # credit that didn't happen.
    notifications_service.send_funding_received(
        profile=profile,
        amount_minor=amount_minor,
        currency=currency,
        transaction_id=result.transaction_id,
    )

    print(f"Funded {email}")
    print(f"  uid:      {uid}")
    print(f"  currency: {currency.value}")
    print(f"  credited: {amount_major}")
    print(f"  balance:  {new_balance} minor units")
    print(f"  tx:       {result.transaction_id}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m scripts.fund_user <email> <amount_major_units>"
        )

    try:
        amount = Decimal(sys.argv[2])
    except InvalidOperation:
        raise SystemExit(f"Invalid amount: {sys.argv[2]!r}")

    _fund(sys.argv[1], amount)