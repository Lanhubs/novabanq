"""Flutterwave virtual account provider.

Placeholder for the real integration. Every method raises
``FundingProviderUnavailableError`` until Flutterwave credentials are
wired in and the actual HTTP calls are written. The file exists so the
provider interface has a named real-world implementation and so
switching from the mock is a one-line change in the factory (see
``app/infra/virtual_accounts/__init__.py``), not a new file.

Raises a typed ``NovaBanqError`` rather than a bare
``NotImplementedError`` so that, if this class is ever reached by
mistake (a factory misconfiguration, ``DEMO_MODE`` unexpectedly
``False`` somewhere it shouldn't be), the failure comes back as a
clean, well-formed API error — the same 502
``FUNDING_PROVIDER_UNAVAILABLE`` response the real integration will
also raise for a genuine Flutterwave outage once it exists, not an
untyped Python exception outside the envelope every other endpoint in
this API returns. There's no factory-level guard here forcing this
class out of production the way ``get_identity_provider()`` explicitly
blocks ``kyc_provider=mock`` in production — this file relies on the
factory choosing correctly. Do not call these methods in production.

Why it is a stub today:

    * The hackathon demo runs against the mock provider. The mock
      exercises the same interface and the same ledger path, with no
      network dependency.
    * Flutterwave's sandbox requires a publicly reachable webhook URL
      for the funding notification, which means Render or a tunnel.
      That is post-hackathon work.
    * Flutterwave currently issues virtual account numbers for NGN
      through the Collect Payments product. Ghanaian and Kenyan
      virtual accounts are not available through the same flow, so a
      real integration would still fall back to the mock for those
      countries.

When the real integration is written, it will:

    1. Read the API key and base URL from ``settings``.
    2. Call ``POST /v3/virtual-account-numbers`` with the customer's
       details.
    3. Parse the response into a ``VirtualAccount``.
    4. Store the mapping from ``provider_ref`` to the owning uid — in
       the existing ``funding_records`` collection, not a new one — so
       the webhook can resolve an incoming payment.

None of that is implemented.
"""

from app.core.constants import Country, Currency, ErrorCode
from app.core.exceptions import NovaBanqError
from app.infra.virtual_accounts.base import (
    VirtualAccount,
    VirtualAccountProvider,
)


class FundingProviderUnavailableError(NovaBanqError):
    """Raised when the funding provider cannot complete a request.

    Covers both this stub's current "not implemented" state and, once
    the real Flutterwave integration replaces it, a genuine outage of
    Flutterwave itself — the client sees the same 502 either way and
    doesn't need to know which case it is.
    """

    status_code = 502
    code = ErrorCode.FUNDING_PROVIDER_UNAVAILABLE
    message = "The funding provider is temporarily unavailable."


class FlutterwaveVirtualAccountProvider(VirtualAccountProvider):
    """Placeholder for the real Flutterwave integration.

    Every method raises ``FundingProviderUnavailableError``. The class
    exists so that ``isinstance`` checks and dependency injection work
    against the same interface as the mock.
    """

    def create_virtual_account(
        self,
        *,
        uid: str,
        account_name: str,
        country: Country,
        currency: Currency,
        email: str,
        phone: str,
    ) -> VirtualAccount:
        """Not implemented. See the module docstring."""
        raise FundingProviderUnavailableError(
            "Flutterwave virtual account creation is not implemented. "
            "The demo uses MockVirtualAccountProvider. Wire the real "
            "integration post-hackathon."
        )

    def get_virtual_account(
        self,
        *,
        provider_ref: str,
    ) -> VirtualAccount | None:
        """Not implemented. See the module docstring."""
        raise FundingProviderUnavailableError(
            "Flutterwave virtual account lookup is not implemented. "
            "The demo uses MockVirtualAccountProvider. Wire the real "
            "integration post-hackathon."
        )