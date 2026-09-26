"""Transactional email templates.

Every transactional email NovaBanq sends is defined here as a small
function that returns an ``EmailContent`` object. Feature services
import the relevant template, call the function, and hand the result
to ``send_email``.

Adding a new email type is one function — no changes to the client,
no changes to any service that already sends other emails.

Design rules:
    * Every template returns both HTML and plaintext.
    * No external template engine (Jinja, etc.) — pure Python f-strings
      keep the module dependency-free and easy to reason about.
    * Styling is inline and minimal — most African email clients strip
      ``<style>`` blocks and external stylesheets.
    * Amounts are formatted via ``app.core.utils.format_amount`` so
      every email renders currency symbols and decimal places
      identically to the rest of the platform.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.constants import Currency
from app.core.utils import format_amount


@dataclass(frozen=True)
class EmailContent:
    """Rendered email content ready for delivery."""

    subject: str
    html: str
    text: str
    tags: list[str]


# ---------------------------------------------------------------------------
# Shared layout
# ---------------------------------------------------------------------------

def _wrap_layout(*, preheader: str, body_html: str) -> str:
    """Wrap email body HTML in the standard NovaBanq layout.

    Args:
        preheader: Preview text shown by email clients next to the subject.
        body_html: The inner HTML of the email.

    Returns:
        Full HTML document string.
    """
    brand = settings.app_name
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{brand}</title>
</head>
<body style="margin:0;padding:0;background:#F2FAF6;font-family:Arial,Helvetica,sans-serif;color:#111827;">
<div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F2FAF6;padding:24px 0;">
  <tr>
    <td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#FFFFFF;border-radius:12px;padding:32px;">
        <tr>
          <td style="padding-bottom:16px;font-size:20px;font-weight:700;color:#2D6A4F;">{brand}</td>
        </tr>
        <tr>
          <td style="font-size:15px;line-height:1.6;color:#111827;">
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="padding-top:32px;font-size:12px;color:#9CA3AF;">
            You are receiving this email because you have a {brand} account.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def render_otp_email(*, code: str, expires_in_minutes: int) -> EmailContent:
    """Email containing a one-time verification code.

    Args:
        code: The plaintext OTP code the user must enter.
        expires_in_minutes: Validity window shown to the user.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    subject = f"Your {settings.app_name} verification code"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Here is your verification code:</p>
<p style="margin:0 0 24px 0;font-size:32px;font-weight:700;letter-spacing:6px;color:#2D6A4F;">{code}</p>
<p style="margin:0 0 8px 0;">This code expires in {expires_in_minutes} minutes.</p>
<p style="margin:0;">If you did not request this code, you can safely ignore this email.</p>
"""

    text = (
        f"Your {settings.app_name} verification code is: {code}\n\n"
        f"This code expires in {expires_in_minutes} minutes.\n"
        "If you did not request this code, you can safely ignore this email."
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"Your verification code expires in {expires_in_minutes} minutes.",
            body_html=body_html,
        ),
        text=text,
        tags=["otp", "email-verification"],
    )


def render_welcome_email(
    *,
    first_name: str,
    account_number: str,
) -> EmailContent:
    """Welcome email sent once, when the user's profile is created.

    Fires from ``POST /users/me`` on first call. The user has already
    verified their email at this point — the email gate runs before
    profile creation — so this is the first message they receive from
    a fully-authenticated NovaBanq account.

    Deliberately does not include the user's @tag. At profile-creation
    time the tag has not been claimed yet; the email instead points at
    tag claim as the next step.

    Args:
        first_name: The user's first name, for the greeting.
        account_number: The user's 10-digit NovaBanq account number,
            generated during profile creation.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    subject = f"Welcome to {brand}, {first_name}"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Hi {first_name},</p>
<p style="margin:0 0 16px 0;">Welcome to {brand}. Send money across Africa in seconds — no markup, no multi-app dance.</p>
<p style="margin:0 0 8px 0;">Your account number is:</p>
<p style="margin:0 0 24px 0;font-size:20px;font-weight:700;letter-spacing:2px;color:#2D6A4F;">{account_number}</p>
<p style="margin:0 0 8px 0;"><strong>Next steps</strong></p>
<ul style="margin:0 0 16px 0;padding-left:20px;">
  <li style="margin-bottom:8px;">Claim your @tag to start receiving money from anywhere in Africa.</li>
  <li style="margin-bottom:8px;">Complete identity verification to unlock higher limits.</li>
</ul>
<p style="margin:0;">Open the app to get started.</p>
"""

    text = (
        f"Hi {first_name},\n\n"
        f"Welcome to {brand}. Send money across Africa in seconds — "
        "no markup, no multi-app dance.\n\n"
        f"Your account number is: {account_number}\n\n"
        "Next steps:\n"
        "  - Claim your @tag to start receiving money from anywhere in Africa.\n"
        "  - Complete identity verification to unlock higher limits.\n\n"
        "Open the app to get started."
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"Your {brand} account is ready.",
            body_html=body_html,
        ),
        text=text,
        tags=["welcome"],
    )


def render_transfer_sent_email(
    *,
    sender_first_name: str,
    recipient_display_name: str,
    recipient_tag: str,
    send_amount_minor: int,
    fee_minor: int,
    total_debit_minor: int,
    sender_currency: Currency,
    transaction_id: str,
) -> EmailContent:
    """Confirmation sent to the sender after a transfer settles.

    Args:
        sender_first_name: The sender's first name, for the greeting.
        recipient_display_name: The recipient's full display name.
        recipient_tag: The recipient's full @tag.
        send_amount_minor: Amount the sender entered, in sender-currency
            minor units.
        fee_minor: Fee charged, in sender-currency minor units.
        total_debit_minor: Total debited from the sender
            (``send_amount_minor + fee_minor``).
        sender_currency: The currency the sender paid in.
        transaction_id: Ledger transaction identifier, shown for
            support purposes.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    send_display = format_amount(send_amount_minor, sender_currency)
    fee_display = format_amount(fee_minor, sender_currency)
    total_display = format_amount(total_debit_minor, sender_currency)

    subject = f"You sent {send_display} to {recipient_display_name}"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Hi {sender_first_name},</p>
<p style="margin:0 0 16px 0;">Your transfer to <strong>{recipient_display_name}</strong> (@{recipient_tag}) has been sent.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px 0;border-collapse:collapse;">
  <tr><td style="padding:8px 0;color:#6B7280;">Amount</td><td style="padding:8px 0;text-align:right;font-weight:600;">{send_display}</td></tr>
  <tr><td style="padding:8px 0;color:#6B7280;">Fee</td><td style="padding:8px 0;text-align:right;">{fee_display}</td></tr>
  <tr><td style="padding:8px 0;color:#6B7280;border-top:1px solid #E5E7EB;">Total debited</td><td style="padding:8px 0;text-align:right;font-weight:700;border-top:1px solid #E5E7EB;">{total_display}</td></tr>
</table>
<p style="margin:0 0 8px 0;font-size:12px;color:#9CA3AF;">Transaction ID: {transaction_id}</p>
<p style="margin:0;">If you did not authorize this transfer, contact support immediately.</p>
"""

    text = (
        f"Hi {sender_first_name},\n\n"
        f"Your transfer to {recipient_display_name} (@{recipient_tag}) "
        "has been sent.\n\n"
        f"Amount:        {send_display}\n"
        f"Fee:           {fee_display}\n"
        f"Total debited: {total_display}\n\n"
        f"Transaction ID: {transaction_id}\n\n"
        "If you did not authorize this transfer, contact support immediately."
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"{total_display} sent to {recipient_display_name}.",
            body_html=body_html,
        ),
        text=text,
        tags=["transfer", "transfer-sent"],
    )


def render_transfer_received_email(
    *,
    recipient_first_name: str,
    sender_display_name: str,
    sender_tag: str,
    receive_amount_minor: int,
    recipient_currency: Currency,
    transaction_id: str,
) -> EmailContent:
    """Notification sent to the recipient after a transfer settles.

    Args:
        recipient_first_name: The recipient's first name, for the
            greeting.
        sender_display_name: The sender's full display name.
        sender_tag: The sender's full @tag.
        receive_amount_minor: Amount the recipient received, in
            recipient-currency minor units.
        recipient_currency: The currency the recipient received in.
        transaction_id: Ledger transaction identifier, shown for
            support purposes.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    receive_display = format_amount(receive_amount_minor, recipient_currency)

    subject = f"You received {receive_display} from {sender_display_name}"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Hi {recipient_first_name},</p>
<p style="margin:0 0 16px 0;">You received <strong>{receive_display}</strong> from <strong>{sender_display_name}</strong> (@{sender_tag}).</p>
<p style="margin:0 0 16px 0;">The money is already in your {brand} balance.</p>
<p style="margin:0 0 8px 0;font-size:12px;color:#9CA3AF;">Transaction ID: {transaction_id}</p>
"""

    text = (
        f"Hi {recipient_first_name},\n\n"
        f"You received {receive_display} from {sender_display_name} "
        f"(@{sender_tag}).\n\n"
        f"The money is already in your {brand} balance.\n\n"
        f"Transaction ID: {transaction_id}"
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"{receive_display} received from {sender_display_name}.",
            body_html=body_html,
        ),
        text=text,
        tags=["transfer", "transfer-received"],
    )


def render_withdrawal_confirmed_email(
    *,
    first_name: str,
    amount_minor: int,
    currency: Currency,
    destination_description: str,
    transaction_id: str,
) -> EmailContent:
    """Confirmation sent when a withdrawal settles.

    Args:
        first_name: The withdrawing user's first name, for the
            greeting.
        amount_minor: Amount withdrawn, in the user's currency minor
            units.
        currency: The currency the amount is denominated in.
        destination_description: Human-readable description of where
            the money went, e.g. "GTBank ••••1234".
        transaction_id: Ledger transaction identifier, shown for
            support purposes.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    amount_display = format_amount(amount_minor, currency)

    subject = f"Withdrawal of {amount_display} confirmed"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Hi {first_name},</p>
<p style="margin:0 0 16px 0;">Your withdrawal of <strong>{amount_display}</strong> has been processed.</p>
<p style="margin:0 0 16px 0;">Destination: <strong>{destination_description}</strong></p>
<p style="margin:0 0 8px 0;font-size:12px;color:#9CA3AF;">Transaction ID: {transaction_id}</p>
<p style="margin:0;">Depending on your bank, funds typically arrive within one business day.</p>
"""

    text = (
        f"Hi {first_name},\n\n"
        f"Your withdrawal of {amount_display} has been processed.\n\n"
        f"Destination: {destination_description}\n\n"
        f"Transaction ID: {transaction_id}\n\n"
        "Depending on your bank, funds typically arrive within one "
        "business day."
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"Your {amount_display} withdrawal has been processed.",
            body_html=body_html,
        ),
        text=text,
        tags=["withdrawal", "withdrawal-confirmed"],
    )


def render_pin_lockout_email(
    *,
    first_name: str,
    lockout_minutes: int,
) -> EmailContent:
    """Security notification sent when a PIN is locked out.

    Fires when the sender exhausts their PIN attempts on a transfer.
    Contains no amounts and no transaction details — this is a security
    event, not a financial one, and the email should read as a warning
    that someone tried something, not as a receipt.

    Args:
        first_name: The user's first name, for the greeting.
        lockout_minutes: How long the PIN entry is locked for.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    subject = f"Your {brand} PIN has been temporarily locked"

    body_html = f"""\
<p style="margin:0 0 16px 0;">Hi {first_name},</p>
<p style="margin:0 0 16px 0;">We detected multiple incorrect PIN attempts on your account. For your security, PIN entry has been locked for <strong>{lockout_minutes} minutes</strong>.</p>
<p style="margin:0 0 16px 0;">If this was you, simply wait and try again with the correct PIN.</p>
<p style="margin:0 0 16px 0;">If this was <strong>not</strong> you, someone may have access to your account. Change your password immediately and contact support.</p>
"""

    text = (
        f"Hi {first_name},\n\n"
        "We detected multiple incorrect PIN attempts on your account. "
        f"For your security, PIN entry has been locked for "
        f"{lockout_minutes} minutes.\n\n"
        "If this was you, simply wait and try again with the correct "
        "PIN.\n\n"
        "If this was NOT you, someone may have access to your account. "
        "Change your password immediately and contact support."
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader="Multiple incorrect PIN attempts detected.",
            body_html=body_html,
        ),
        text=text,
        tags=["security", "pin-lockout"],
    )