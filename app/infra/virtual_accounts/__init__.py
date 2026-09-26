"""Virtual account providers.

Exposes a factory that returns the active virtual account provider.
For the hackathon the mock is always returned; the real Flutterwave
integration is a placeholder until credentials and a webhook URL are
wired in (see ``flutterwave.py`` for why).

Switching providers later is a one-line change in
``get_virtual_account_provider`` — nothing downstream needs to change,
because both implementations satisfy the same
``VirtualAccountProvider`` interface.

Note on ``settings.demo_mode``: unlike ``get_identity_provider()``,
which branches on ``settings.kyc_provider`` and explicitly blocks the
mock in production, this factory does not consult ``demo_mode`` at
all. That's deliberate, not an oversight — don't "fix" it without
reading this first. ``FlutterwaveVirtualAccountProvider`` isn't a
working alternative yet; every one of its methods raises
``FundingProviderUnavailableError`` unconditionally. Branching on
``demo_mode`` today would mean any deployment with
``demo_mode=False`` gets a funding feature that's permanently broken,
instead of falling back to a working (if fake) one. Once the real
integration is written, switch the hardcoded return below to branch
on ``settings.demo_mode`` (or ``settings.is_production``, matching
the KYC pattern) — but not before then.
"""

from app.infra.virtual_accounts.base import (
    VirtualAccount,
    VirtualAccountProvider,
)
from app.infra.virtual_accounts.flutterwave import (
    FlutterwaveVirtualAccountProvider,
    FundingProviderUnavailableError,
)
from app.infra.virtual_accounts.mock import MockVirtualAccountProvider


def get_virtual_account_provider() -> VirtualAccountProvider:
    """Return the active virtual account provider.

    Always returns the mock for the hackathon, regardless of
    ``settings.demo_mode`` — see the module docstring for why this
    doesn't branch on that setting yet. When the real Flutterwave
    integration is written and its credentials and webhook URL are in
    place, this function is the single point of change — swap
    ``MockVirtualAccountProvider()`` for a ``settings``-driven choice
    between it and ``FlutterwaveVirtualAccountProvider()``.
    """
    return MockVirtualAccountProvider()


__all__ = [
    "FlutterwaveVirtualAccountProvider",
    "FundingProviderUnavailableError",
    "MockVirtualAccountProvider",
    "VirtualAccount",
    "VirtualAccountProvider",
    "get_virtual_account_provider",
]