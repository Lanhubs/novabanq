"""Brevo transactional email client.

Thin HTTP wrapper around Brevo's transactional email API. This module
owns only the delivery concern — auth headers, timeouts, and error
mapping. Rendering lives in ``templates.py``; business orchestration
lives in the feature services that call ``send_email``.

Reference:
    https://developers.brevo.com/reference/sendtransacemail
"""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import NovaBanqError

logger = logging.getLogger(__name__)

_BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
_REQUEST_TIMEOUT_SECONDS = 10.0


class EmailDeliveryError(NovaBanqError):
    """Raised when a transactional email cannot be delivered."""

    status_code = 502
    message = "Email delivery failed. Please try again shortly."


def send_email(
    *,
    to_email: str,
    to_name: str | None = None,
    subject: str,
    html_content: str,
    text_content: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Send a transactional email via Brevo.

    Args:
        to_email: Recipient address.
        to_name: Optional recipient display name.
        subject: Email subject line.
        html_content: Rendered HTML body.
        text_content: Optional plaintext fallback body.
        tags: Optional list of Brevo tags for analytics filtering.

    Returns:
        Parsed JSON response from Brevo, including the message id.

    Raises:
        EmailDeliveryError: If Brevo rejects the request or the network
            call fails.
    """
    api_key, sender_email, sender_name = settings.require_brevo_config()

    payload: dict[str, Any] = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content
    if tags:
        payload["tags"] = tags

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(_BREVO_API_URL, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.error("Brevo request timed out for recipient=%s.", to_email)
        raise EmailDeliveryError("Email provider timed out.") from exc
    except httpx.HTTPError as exc:
        logger.exception("Brevo request failed for recipient=%s.", to_email)
        raise EmailDeliveryError("Email provider is unreachable.") from exc

    if response.status_code >= 400:
        logger.error(
            "Brevo rejected email for recipient=%s status=%s body=%s",
            to_email,
            response.status_code,
            response.text,
        )
        raise EmailDeliveryError()

    logger.info("Brevo accepted email for recipient=%s.", to_email)
    return response.json()