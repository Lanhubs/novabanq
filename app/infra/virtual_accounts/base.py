"""Virtual account provider interface.

Defines the abstract contract every virtual account provider must
satisfy. The mock and real (Flutterwave) implementations both return
the same ``VirtualAccount`` shape, so the funding service does not
know or care which one is active.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.constants import Country, Currency


@dataclass(frozen=True)
class VirtualAccount:
    """A virtual account that can receive deposits.

    The ``provider_ref`` is the provider's own identifier for this
    account. It is stable across the account's lifetime and is the
    only field the webhook needs to look up the owning user.
    """

    account_number: str
    bank_name: str
    account_name: str
    provider_ref: str
    currency: Currency
    country: Country


class VirtualAccountProvider(ABC):
    """Interface for creating and looking up virtual accounts."""

    @abstractmethod
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
        """Create a virtual account for a user.

        ``country`` and ``currency`` are both provided because they are
        not one-to-one: Senegal and Ivory Coast share XOF but are
        different countries with potentially different payment rails.
        The mock provider ignores ``country``; the real Flutterwave
        provider uses it to select the correct rail.

        Idempotent: calling twice for the same uid returns the same
        account, never creates a second one.
        """

    @abstractmethod
    def get_virtual_account(
        self,
        *,
        provider_ref: str,
    ) -> VirtualAccount | None:
        """Return a virtual account by its provider reference.

        Returns ``None`` if no account exists with that reference.
        Used by the webhook to resolve an incoming payment to the
        user it belongs to.
        """