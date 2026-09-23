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
"""

from dataclasses import dataclass

from app.core.config import settings


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