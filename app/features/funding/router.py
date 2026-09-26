"""Funding HTTP endpoints.

Two routes, with two different authentication models:

    * ``POST /funding/virtual-account`` — get-or-create the caller's
      virtual account. Authenticated via Firebase ID token, same as
      every other user-facing endpoint.

    * ``POST /webhooks/flutterwave`` — receives deposit notifications
      from Flutterwave. Not authenticated by Firebase (Flutterwave
      does not carry a user token); authenticated by the provider's
      ``verif-hash`` header instead.

Both handlers are ``def``, not ``async def`` — same reason as every
other router in this codebase. Firestore and the email client are
synchronous.

Note on webhook ordering:
    The webhook's signature is verified inside the handler, which
    runs **after** FastAPI has parsed and validated the request body
    against ``WebhookPayload``. A malformed body therefore returns a
    422 rather than a 401, even for an unauthenticated caller. This
    is a deliberate acceptance of a small, bounded exposure — no state
    changes occur before the signature check, so the only thing an
    unauthenticated caller can learn from a 422 is the shape of a
    webhook payload that is already published in ``/openapi.json``.
    Moving verification ahead of body parsing would require either a
    path-matching middleware (fragile) or making this one endpoint
    async and calling the sync service from a threadpool (complexity
    not justified by the risk). Revisit when the real Flutterwave
    integration lands.
"""

import hmac
from typing import Any

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.exceptions import NovaBanqError
from app.core.security import CurrentUid
from app.features.funding import service
from app.features.funding.schemas import (
    VirtualAccountResponse,
    WebhookAck,
    WebhookPayload,
)
from app.infra.virtual_accounts import get_virtual_account_provider
from app.infra.virtual_accounts.mock import MockVirtualAccountProvider

router = APIRouter()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class InvalidWebhookSignatureError(NovaBanqError):
    """Raised when the Flutterwave webhook signature is missing or wrong.

    The response is a 401 — Flutterwave treats non-2xx as a delivery
    failure and will retry. That is the correct behavior for a
    signature mismatch: it either means the header was stripped in
    transit (transient) or someone is POSTing directly (worth
    retrying-and-failing loudly, not silently accepting).

    A missing `flutterwave_secret_hash` on the server also surfaces as
    this error, so a misconfigured deployment refuses to accept
    webhooks rather than accepting them unverified.
    """

    status_code = 401
    code = ErrorCode.AUTH_INVALID
    message = "Invalid webhook signature."


# ---------------------------------------------------------------------------
# Envelope helper (inline per router, same as every other module)
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/funding/virtual-account",
    response_model=dict[str, Any],
    summary="Get or create the authenticated user's virtual account",
    description=(
        "Returns the user's virtual account number, bank name, and "
        "currency. Idempotent: calling this more than once for the "
        "same user returns the same account, never a second one.\n\n"
        "The user gives this account number to their bank or mobile "
        "money app to make a deposit. When the deposit arrives, "
        "NovaBanq receives a webhook from the provider and credits "
        "the user's balance automatically."
    ),
)
def get_or_create_virtual_account(uid: CurrentUid) -> dict[str, Any]:
    """Return the user's virtual account, creating it if absent."""
    result: VirtualAccountResponse = service.create_virtual_account(uid)
    return _ok(result.model_dump())


@router.post(
    "/webhooks/flutterwave",
    response_model=dict[str, Any],
    summary="Receive a Flutterwave deposit webhook",
    description=(
        "Called by Flutterwave when a deposit to a virtual account "
        "settles. Verifies the provider's `verif-hash` header before "
        "crediting.\n\n"
        "Returns 200 for every well-formed event, whether the deposit "
        "was credited, was a duplicate delivery, or was rejected as "
        "corrupt. Returns 401 only when the signature check fails — "
        "that is a genuine delivery failure and Flutterwave should "
        "retry. A malformed request body returns 422 before the "
        "signature is examined; see the module docstring for why that "
        "is acceptable."
    ),
)
def flutterwave_webhook(
    request: Request,
    payload: WebhookPayload,
) -> dict[str, Any]:
    """Verify the signature, then process the deposit event."""
    _verify_webhook_signature(request)
    ack: WebhookAck = service.handle_webhook(payload)
    return _ok(ack.model_dump())


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_webhook_signature(request: Request) -> None:
    """Verify the Flutterwave ``verif-hash`` header.

    Skipped **only** when the active virtual account provider is the
    mock. Whenever the real provider is wired in, verification runs
    unconditionally.

    This is deliberately not gated on ``settings.demo_mode`` or any
    other flag. ``demo_mode`` defaults to ``True``, so a flag-based
    gate would put the *insecure* state on as the default — a
    production deployment that forgot to set ``DEMO_MODE=false``
    would accept unsigned webhooks and let anyone credit arbitrary
    accounts. Gating on the provider instead means there is exactly
    one source of truth: the factory in
    ``app.infra.virtual_accounts`` either returned the mock (safe to
    skip verification — no real money can arrive through it) or it
    returned something else (verification is mandatory, no override).

    When verification runs and the server has no
    ``FLUTTERWAVE_SECRET_HASH`` configured, the webhook returns 401
    rather than accepting the payload. A misconfigured deployment
    refuses to process webhooks instead of processing them unverified.

    The comparison uses ``hmac.compare_digest`` so that the time
    taken to reject a wrong signature is independent of how many
    leading bytes matched the correct one. A short-circuiting ``!=``
    would leak the correct hash byte-by-byte to an attacker who can
    measure response times.
    """
    provider = get_virtual_account_provider()
    if isinstance(provider, MockVirtualAccountProvider):
        return

    header = request.headers.get("verif-hash")
    expected = settings.flutterwave_secret_hash

    if not expected:
        raise InvalidWebhookSignatureError(
            "Server is not configured with a Flutterwave secret hash."
        )
    if not header or not hmac.compare_digest(header, expected):
        raise InvalidWebhookSignatureError()