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
    * Amounts are formatted via ``app.core.utils.format_amount`` so
      every email renders currency symbols and decimal places
      identically to the rest of the platform.
    * All templates share ``_wrap_layout`` — one shell, one set of
      typographic conventions. The shell targets XHTML 1.0
      transitional so Outlook, Gmail, and Apple Mail all render it
      the same way.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.constants import Currency
from app.core.utils import format_amount


# ---------------------------------------------------------------------------
# Brand constants
#
# Every template references these, never the values directly, so a
# change to the logo, the palette, or the footer copy lands in one
# place.
# ---------------------------------------------------------------------------

_LOGO_URL = (
    "https://res.cloudinary.com/duaal95pl/image/upload/"
    "v1790459753/emaila_images/a8lmtihlrlpco3rsgb5a.png"
)
_BRAND_GREEN = "#22C55E"
_TEXT_PRIMARY = "#111111"
_TEXT_SECONDARY = "#6B7280"
_TEXT_MUTED = "#9CA3AF"
_FONT_STACK = "Arial, Helvetica, sans-serif"


@dataclass(frozen=True)
class EmailContent:
    """Rendered email content ready for delivery."""

    subject: str
    html: str
    text: str
    tags: list[str]


# ---------------------------------------------------------------------------
# Shared shell
# ---------------------------------------------------------------------------

def _wrap_layout(*, preheader: str, body_html: str) -> str:
    """Wrap email body HTML in the standard NovaBanq shell.

    The shell is a single-column, 600px-max-width layout with the
    NovaBanq logo at the top, the body content in the middle, and a
    transactional footer at the bottom. It is written as XHTML 1.0
    transitional with Outlook conditional comments so that Outlook,
    Gmail, Apple Mail, and mobile clients all render it consistently.

    Args:
        preheader: Preview text shown by email clients next to the
            subject. Rendered in a hidden div so it does not appear
            in the visible body.
        body_html: The inner HTML of the email. This is what each
            ``render_*_email`` function builds.

    Returns:
        Full HTML document string.
    """
    brand = settings.app_name
    return f"""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="x-apple-disable-message-reformatting" />
  <title>{brand}</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style type="text/css">
    body {{ margin: 0; padding: 0; width: 100% !important; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    #outlook a {{ padding: 0; }}
    img {{ outline: none; text-decoration: none; -ms-interpolation-mode: bicubic; }}
    a img {{ border: none; }}
    table {{ border-collapse: collapse !important; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    th {{ font-weight: normal; }}
    p {{ margin: 0 0 14px 0; }}

    @media only screen and (max-width: 600px) {{
      .container {{ width: 100% !important; max-width: 100% !important; }}
      .outer-td {{ padding: 8px 6px !important; }}
      .email-container-inner {{ padding: 0 !important; }}
      .stack-column {{ display: block !important; width: 100% !important; }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">
  <div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; width: 100% !important; margin: 0; padding: 0;">
    <tr>
      <td class="outer-td" align="center" style="padding: 12px 8px; background-color: #ffffff;">
        <!--[if mso]>
        <table role="presentation" width="600" border="0" cellspacing="0" cellpadding="0" style="width: 600px; margin: 0 auto;">
        <tr>
        <td>
        <![endif]-->
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" class="container" style="max-width: 600px; width: 100%; margin: 0 auto; background-color: #ffffff; border-collapse: collapse;">
          <tr>
            <td class="email-container-inner" style="padding: 0; font-size: 16px; line-height: 1.6; color: {_TEXT_PRIMARY}; word-break: break-word;">

              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
                <tr>
                  <td align="left" style="padding-top: 0px; padding-bottom: 24px;">
                    <img src="{_LOGO_URL}" alt="{brand}" width="150" style="display: block; border: 0; outline: none; height: auto; width: 150px;" />
                  </td>
                </tr>
              </table>

              {body_html}

              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
                <tr>
                  <td align="center" style="margin-top: 24px; padding-top: 24px; font-family: {_FONT_STACK}; font-size: 16px; font-weight: 400; color: {_TEXT_PRIMARY}; text-align: center; line-height: 1.5; word-break: break-word;">
                    <p style="margin: 0 0 14px 0; padding: 0; line-height: 1.6; mso-line-height-rule: exactly;"><span style="color: {_TEXT_MUTED}; font-family: {_FONT_STACK}; font-size: 12px;">You are receiving this email because you have a {brand} account.</span></p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>
        </table>
        <!--[if mso]>
        </td>
        </tr>
        </table>
        <![endif]-->
      </td>
    </tr>
  </table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Body-block helpers
#
# Each helper produces one Outlook-safe table-wrapped block. They all
# share the same inline-styling conventions: `mso-line-height-rule:
# exactly` on every paragraph, `word-break: break-word` on every cell,
# and `role="presentation"` on every table.
# ---------------------------------------------------------------------------

def _paragraph(text_html: str, *, top_margin: int = 0) -> str:
    """Render a standard body paragraph.

    Args:
        text_html: The paragraph content, already HTML-escaped or
            containing intentional inline markup.
        top_margin: Vertical space above the paragraph, in pixels.

    Returns:
        A single table block wrapping the paragraph.
    """
    return f"""\
<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
  <tr>
    <td align="left" style="margin-top: {top_margin}px; padding: 0; font-family: {_FONT_STACK}; font-size: 16px; font-weight: 400; color: {_TEXT_PRIMARY}; text-align: left; line-height: 1.5; word-break: break-word;">
      <p style="margin: 0 0 14px 0; padding: 0; line-height: 1.6; mso-line-height-rule: exactly;">{text_html}</p>
    </td>
  </tr>
</table>"""


def _heading(text: str, *, top_margin: int = 24) -> str:
    """Render a section heading."""
    return f"""\
<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
  <tr>
    <td align="left" style="margin-top: {top_margin}px; padding: 0; font-family: {_FONT_STACK}; font-size: 18px; font-weight: 700; color: {_TEXT_PRIMARY}; text-align: left; line-height: 1.4; word-break: break-word;">
      <p style="margin: 0 0 14px 0; padding: 0; line-height: 1.6; mso-line-height-rule: exactly;">{text}</p>
    </td>
  </tr>
</table>"""


def _big_number(text: str, *, top_margin: int = 12) -> str:
    """Render a large monospaced-feeling value, e.g. an OTP code.

    Uses the brand green and a large size so the number is the first
    thing the eye lands on. Spacing between digits is added by the
    caller — this helper does not format the value.
    """
    return f"""\
<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
  <tr>
    <td align="left" style="margin-top: {top_margin}px; padding: 0; font-family: {_FONT_STACK}; font-size: 48px; font-weight: bold; color: {_BRAND_GREEN}; text-align: left; line-height: 1.2; word-break: break-word;">
      <p style="margin: 0 0 14px 0; padding: 0; line-height: 1.2; mso-line-height-rule: exactly;">{text}</p>
    </td>
  </tr>
</table>"""


def _key_value_rows(rows: list[tuple[str, str]]) -> str:
    """Render a compact label/value list, e.g. an amount breakdown.

    Args:
        rows: A list of ``(label, value_html)`` tuples. Rendered top
            to bottom in the order given. The final row is rendered
            with a heavier weight and a top border, matching how a
            receipt distinguishes its total from its components.

    Returns:
        A single table block wrapping the rows.
    """
    rendered = []
    last = len(rows) - 1
    for index, (label, value) in enumerate(rows):
        is_last = index == last
        border_top = "border-top: 1px solid #E5E7EB; " if is_last else ""
        value_weight = "700" if is_last else "600"
        rendered.append(
            f'    <tr>'
            f'<td style="padding: 8px 0; {border_top}font-family: {_FONT_STACK}; '
            f'font-size: 15px; color: {_TEXT_SECONDARY};">{label}</td>'
            f'<td style="padding: 8px 0; {border_top}text-align: right; '
            f'font-weight: {value_weight}; font-family: {_FONT_STACK}; '
            f'font-size: 15px; color: {_TEXT_PRIMARY};">{value}</td>'
            f'</tr>'
        )

    return f"""\
<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; margin: 8px 0 16px 0; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
{chr(10).join(rendered)}
</table>"""


def _transaction_id_line(transaction_id: str) -> str:
    """Render the muted transaction-id footer line."""
    return f"""\
<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="width: 100%; border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">
  <tr>
    <td align="left" style="padding: 0; font-family: {_FONT_STACK}; font-size: 12px; color: {_TEXT_MUTED}; text-align: left; line-height: 1.5; word-break: break-word;">
      <p style="margin: 0 0 14px 0; padding: 0; line-height: 1.6; mso-line-height-rule: exactly;">Transaction ID: {transaction_id}</p>
    </td>
  </tr>
</table>"""


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
    brand = settings.app_name
    subject = f"Your {brand} verification code"

    # Space the digits so the code is legible at 48px.
    spaced_code = " ".join(code)

    body_html = "".join([
        _paragraph(f"Hi there,"),
        _paragraph("Here is your verification code:", top_margin=16),
        _big_number(spaced_code),
        _paragraph(
            f"This code expires in {expires_in_minutes} minutes.",
            top_margin=6,
        ),
        _paragraph(
            "If you did not request this code, you can safely ignore "
            "this email.",
        ),
    ])

    text = (
        f"Your {brand} verification code is: {code}\n\n"
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

    body_html = "".join([
        _paragraph(f"Hi {first_name},"),
        _paragraph(
            f"Welcome to {brand}. Send money across Africa in seconds "
            "— no markup, no multi-app dance.",
            top_margin=8,
        ),
        _heading("Your account number", top_margin=24),
        _big_number(account_number, top_margin=6),
        _heading("Next steps", top_margin=16),
        _paragraph(
            "1. Claim your @tag to start receiving money from anywhere "
            "in Africa.",
        ),
        _paragraph(
            "2. Complete identity verification to unlock higher limits.",
        ),
        _paragraph("Open the app to get started.", top_margin=8),
    ])

    text = (
        f"Hi {first_name},\n\n"
        f"Welcome to {brand}. Send money across Africa in seconds — "
        "no markup, no multi-app dance.\n\n"
        f"Your account number is: {account_number}\n\n"
        "Next steps:\n"
        "  1. Claim your @tag to start receiving money from anywhere in Africa.\n"
        "  2. Complete identity verification to unlock higher limits.\n\n"
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

    body_html = "".join([
        _paragraph(f"Hi {sender_first_name},"),
        _paragraph(
            f"Your transfer to <strong>{recipient_display_name}</strong> "
            f"(@{recipient_tag}) has been sent.",
            top_margin=8,
        ),
        _key_value_rows([
            ("Amount", send_display),
            ("Fee", fee_display),
            ("Total debited", total_display),
        ]),
        _transaction_id_line(transaction_id),
        _paragraph(
            "If you did not authorize this transfer, contact support "
            "immediately.",
        ),
    ])

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

    body_html = "".join([
        _paragraph(f"Hi {recipient_first_name},"),
        _paragraph(
            f"You received <strong>{receive_display}</strong> from "
            f"<strong>{sender_display_name}</strong> (@{sender_tag}).",
            top_margin=8,
        ),
        _paragraph(
            f"The money is already in your {brand} balance and ready "
            "to send.",
        ),
        _transaction_id_line(transaction_id),
    ])

    text = (
        f"Hi {recipient_first_name},\n\n"
        f"You received {receive_display} from {sender_display_name} "
        f"(@{sender_tag}).\n\n"
        f"The money is already in your {brand} balance and ready to send.\n\n"
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

    body_html = "".join([
        _paragraph(f"Hi {first_name},"),
        _paragraph(
            f"Your withdrawal of <strong>{amount_display}</strong> has "
            "been processed.",
            top_margin=8,
        ),
        _key_value_rows([
            ("Amount", amount_display),
            ("Destination", destination_description),
        ]),
        _transaction_id_line(transaction_id),
        _paragraph(
            "Depending on your bank, funds typically arrive within one "
            "business day.",
        ),
    ])

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

    body_html = "".join([
        _paragraph(f"Hi {first_name},"),
        _paragraph(
            "We detected multiple incorrect PIN attempts on your "
            f"account. For your security, PIN entry has been locked "
            f"for <strong>{lockout_minutes} minutes</strong>.",
            top_margin=8,
        ),
        _paragraph(
            "If this was you, simply wait and try again with the "
            "correct PIN.",
        ),
        _paragraph(
            "If this was <strong>not</strong> you, someone may have "
            "access to your account. Change your password immediately "
            "and contact support.",
        ),
    ])

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


def render_funding_received_email(
    *,
    first_name: str,
    amount_minor: int,
    currency: Currency,
    transaction_id: str,
) -> EmailContent:
    """Notification sent when a deposit credits the user's balance.

    Fires from the funding webhook after the ledger commits a FUNDING
    transaction. Unlike the transfer emails, there is no counterparty
    — money arrived from outside the ledger, via a virtual account
    deposit. The email reflects that: it says how much landed and in
    what currency, and stops.

    Args:
        first_name: The user's first name, for the greeting.
        amount_minor: Amount credited, in the currency's minor units.
        currency: The currency the deposit arrived in.
        transaction_id: Ledger transaction identifier, shown for
            support purposes.

    Returns:
        Rendered ``EmailContent`` ready for ``send_email``.
    """
    brand = settings.app_name
    amount_display = format_amount(amount_minor, currency)

    subject = f"You received {amount_display} in your {brand} account"

    body_html = "".join([
        _paragraph(f"Hi {first_name},"),
        _paragraph(
            f"Your deposit of <strong>{amount_display}</strong> has "
            "arrived.",
            top_margin=8,
        ),
        _key_value_rows([
            ("Amount", amount_display),
            ("Status", "Credited"),
        ]),
        _paragraph(
            f"The money is already in your {brand} balance and ready "
            "to send.",
        ),
        _transaction_id_line(transaction_id),
    ])

    text = (
        f"Hi {first_name},\n\n"
        f"Your deposit of {amount_display} has arrived.\n\n"
        f"Amount: {amount_display}\n"
        "Status: Credited\n\n"
        f"The money is already in your {brand} balance and ready to send.\n\n"
        f"Transaction ID: {transaction_id}"
    )

    return EmailContent(
        subject=subject,
        html=_wrap_layout(
            preheader=f"{amount_display} deposited to your account.",
            body_html=body_html,
        ),
        text=text,
        tags=["funding", "funding-received"],
    )