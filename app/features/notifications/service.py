"""Notification service.

Sends transactional emails triggered by user actions. Five public
functions, one per notification type. Each one:

    1. Reads the recipient's email from their profile.
    2. Skips silently (logging a warning) if the email is missing.
    3. Renders the appropriate template.
    4. Calls ``send_email``.
    5. Catches ``EmailDeliveryError``, logs it, and returns.

The last point is critical: **a notification failure must never
propagate to the caller.** A successful transfer must not become a
500 because Brevo is down. Money has already moved by the time these
functions run; the email is best-effort and the transfer is not.

These functions are called synchronously from the feature services
that trigger them. That keeps the service layers HTTP-free (no
``BackgroundTasks`` coupling) and matches the call shape of
``ledger.service.debit_and_credit``. If email volume ever justifies
it, moving to a queue is a change at the call sites, not here.
"""

import logging
from typing import Any

from app.core.constants import PIN_LOCKOUT_MINUTES, Currency
from app.infra.email.client import EmailDeliveryError, send_email
from app.infra.email.templates import (
    render_pin_lockout_email,
    render_transfer_received_email,
    render_transfer_sent_email,
    render_welcome_email,
    render_withdrawal_confirmed_email,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_welcome(*, profile: dict[str, Any]) -> None:
    """Send the welcome email after profile creation.

    Fires from ``users_service.create_profile`` on first call, once
    per user. The email gate has already passed by the time this runs,
    so the address is known deliverable.

    Args:
        profile: The newly created user profile, as returned by
            ``users_service.create_profile``. Must contain ``email``,
            ``first_name``, and ``account_number``.
    """
    to_email = _email_of(profile)
    if to_email is None:
        return

    first_name = _first_name_of(profile)
    account_number = profile.get("account_number") or ""

    content = render_welcome_email(
        first_name=first_name,
        account_number=account_number,
    )
    _deliver(
        to_email=to_email,
        to_name=first_name,
        content=content,
        event="welcome",
    )


def send_transfer_sent(
    *,
    sender_profile: dict[str, Any],
    recipient_display_name: str,
    recipient_tag: str,
    send_amount_minor: int,
    fee_minor: int,
    total_debit_minor: int,
    sender_currency: Currency,
    transaction_id: str,
) -> None:
    """Notify the sender that their transfer settled.

    Args:
        sender_profile: The sender's user profile.
        recipient_display_name: The recipient's full display name.
        recipient_tag: The recipient's full @tag.
        send_amount_minor: Amount sent, in sender-currency minor units.
        fee_minor: Fee charged, in sender-currency minor units.
        total_debit_minor: Total debited from the sender.
        sender_currency: The sender's currency.
        transaction_id: Ledger transaction identifier.
    """
    to_email = _email_of(sender_profile)
    if to_email is None:
        return

    content = render_transfer_sent_email(
        sender_first_name=_first_name_of(sender_profile),
        recipient_display_name=recipient_display_name,
        recipient_tag=recipient_tag,
        send_amount_minor=send_amount_minor,
        fee_minor=fee_minor,
        total_debit_minor=total_debit_minor,
        sender_currency=sender_currency,
        transaction_id=transaction_id,
    )
    _deliver(
        to_email=to_email,
        to_name=_display_name_of(sender_profile),
        content=content,
        event="transfer-sent",
    )


def send_transfer_received(
    *,
    recipient_profile: dict[str, Any],
    sender_display_name: str,
    sender_tag: str,
    receive_amount_minor: int,
    recipient_currency: Currency,
    transaction_id: str,
) -> None:
    """Notify the recipient that money arrived.

    Args:
        recipient_profile: The recipient's user profile.
        sender_display_name: The sender's full display name.
        sender_tag: The sender's full @tag.
        receive_amount_minor: Amount received, in recipient-currency
            minor units.
        recipient_currency: The recipient's currency.
        transaction_id: Ledger transaction identifier.
    """
    to_email = _email_of(recipient_profile)
    if to_email is None:
        return

    content = render_transfer_received_email(
        recipient_first_name=_first_name_of(recipient_profile),
        sender_display_name=sender_display_name,
        sender_tag=sender_tag,
        receive_amount_minor=receive_amount_minor,
        recipient_currency=recipient_currency,
        transaction_id=transaction_id,
    )
    _deliver(
        to_email=to_email,
        to_name=_display_name_of(recipient_profile),
        content=content,
        event="transfer-received",
    )


def send_withdrawal_confirmed(
    *,
    profile: dict[str, Any],
    amount_minor: int,
    currency: Currency,
    destination_description: str,
    transaction_id: str,
) -> None:
    """Notify the user that a withdrawal settled.

    Args:
        profile: The withdrawing user's profile.
        amount_minor: Amount withdrawn, in minor units.
        currency: The currency the amount is in.
        destination_description: Human-readable destination, e.g.
            "GTBank ••••1234".
        transaction_id: Ledger transaction identifier.
    """
    to_email = _email_of(profile)
    if to_email is None:
        return

    content = render_withdrawal_confirmed_email(
        first_name=_first_name_of(profile),
        amount_minor=amount_minor,
        currency=currency,
        destination_description=destination_description,
        transaction_id=transaction_id,
    )
    _deliver(
        to_email=to_email,
        to_name=_display_name_of(profile),
        content=content,
        event="withdrawal-confirmed",
    )


def send_pin_lockout(*, profile: dict[str, Any]) -> None:
    """Notify the user that their PIN was locked out.

    Fires from the transfer execute path when ``PinLockedError`` is
    raised. Contains no amounts and no transaction details — it's a
    security notification, not a receipt.

    Args:
        profile: The locked-out user's profile.
    """
    to_email = _email_of(profile)
    if to_email is None:
        return

    content = render_pin_lockout_email(
        first_name=_first_name_of(profile),
        lockout_minutes=PIN_LOCKOUT_MINUTES,
    )
    _deliver(
        to_email=to_email,
        to_name=_display_name_of(profile),
        content=content,
        event="pin-lockout",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _email_of(profile: dict[str, Any]) -> str | None:
    """Return the profile's email, or None if missing.

    A missing email is a valid state (Google Sign-In user with no
    recorded address, or a corrupt profile) and must not raise — the
    caller has already done the money-moving work and the notification
    is best-effort. Logs at warning so the case is visible.
    """
    email = profile.get("email")
    if not isinstance(email, str) or not email.strip():
        logger.warning(
            "Skipping notification: no email on profile uid=%s.",
            profile.get("uid", "<unknown>"),
        )
        return None
    return email


def _first_name_of(profile: dict[str, Any]) -> str:
    """Return the profile's first name, or a generic fallback.

    Templates use this in greetings; an empty greeting ("Hi ,")
    would look broken in a customer's inbox, so fall back to
    "there" — the standard friendly-neutral placeholder.
    """
    name = profile.get("first_name")
    if not isinstance(name, str) or not name.strip():
        return "there"
    return name.strip()


def _display_name_of(profile: dict[str, Any]) -> str:
    """Join the profile's name fields into a single display name.

    Mirrors the logic in ``transfers/service.py``'s ``_display_name``
    so a given user's display name is identical everywhere it appears.
    """
    parts = [
        profile.get("first_name", ""),
        profile.get("middle_name", ""),
        profile.get("last_name", ""),
    ]
    joined = " ".join(p for p in parts if p).strip()
    return joined or "there"


def _deliver(
    *,
    to_email: str,
    to_name: str,
    content: Any,
    event: str,
) -> None:
    """Send a rendered email, swallowing all delivery failures.

    This is the single place in the notification pipeline where
    exceptions from the email provider are caught. Every caller
    above relies on this guarantee: a notification failure must
    never propagate to the money-movement path.

    Catches ``EmailDeliveryError`` (Brevo rejection, timeout, network
    failure) and any unexpected exception. Both are logged; neither
    is re-raised.
    """
    try:
        send_email(
            to_email=to_email,
            to_name=to_name,
            subject=content.subject,
            html_content=content.html,
            text_content=content.text,
            tags=content.tags,
        )
        logger.info("Sent %s notification to %s.", event, to_email)
    except EmailDeliveryError:
        logger.exception(
            "Email provider rejected %s notification for %s.",
            event,
            to_email,
        )
    except Exception:  # noqa: BLE001 — never let a notification break money movement
        logger.exception(
            "Unexpected error sending %s notification to %s.",
            event,
            to_email,
        )