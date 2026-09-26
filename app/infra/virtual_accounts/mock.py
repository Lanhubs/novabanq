"""Mock virtual account provider.

Deterministic, in-process, no network. Used in DEMO_MODE and in
tests.

The account *number* is derived deterministically from
``(uid, country, currency)`` — the same inputs always produce the
same 10-digit number, so nothing needs to be stored on this side to
reproduce it.

The ``provider_ref`` is **not** the uid. It is a random, prefixed
value generated on each call. That is intentional: the funding
service is responsible for storing the mapping from ``provider_ref``
back to the owning user, exactly as it will for the real Flutterwave
integration where the reference is opaque. Reusing the uid here
would let a buggy webhook handler that skips the reverse lookup
"work" in the mock and only fail in production.

The ``mock_`` prefix mirrors the bank name convention
(``"NovaBanq MFB"`` etc.) — demo artifacts should be legible as demo
artifacts in logs and in Firestore, not silently indistinguishable
from real references.
"""

import hashlib
import uuid

from app.core.constants import Country, Currency
from app.infra.virtual_accounts.base import (
    VirtualAccount,
    VirtualAccountProvider,
)


# Bank name shown next to the account number, keyed by country. Each
# country gets a distinct name so the demo UI makes the country
# obvious without needing to encode it in the account digits.
_BANK_NAMES: dict[Country, str] = {
    Country.NIGERIA: "NovaBanq MFB",
    Country.GHANA: "NovaBanq GH",
    Country.KENYA: "NovaBanq KE",
    Country.SENEGAL: "NovaBanq SN",
    Country.IVORY_COAST: "NovaBanq CI",
    Country.SOUTH_AFRICA: "NovaBanq ZA",
}


class MockVirtualAccountProvider(VirtualAccountProvider):
    """Deterministic in-memory provider for the demo."""

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
        """Return a virtual account for the uid.

        The account number is derived deterministically. The
        ``provider_ref`` is a fresh random value on every call — the
        caller is expected to persist it against the user, and to
        check first whether a record already exists. Calling this
        method twice for the same uid and discarding the first result
        will orphan the first ``provider_ref``; the funding service
        is responsible for the get-or-create semantics.

        The email and phone arguments are accepted for interface
        parity but unused — the real provider needs them, the mock
        does not.
        """
        return self._account_for(
            uid=uid,
            account_name=account_name,
            country=country,
            currency=currency,
        )

    def get_virtual_account(
        self,
        *,
        provider_ref: str,
    ) -> VirtualAccount | None:
        """Not supported by the mock.

        The mock does not store accounts; the funding service does.
        This method exists only so the mock and the real provider have
        the same interface shape.

        Returns ``None`` unconditionally.
        """
        return None

    def _account_for(
        self,
        *,
        uid: str,
        account_name: str,
        country: Country,
        currency: Currency,
    ) -> VirtualAccount:
        """Build a virtual account for the uid."""
        digest = hashlib.sha256(
            f"{uid}:{country.value}:{currency.value}".encode("utf-8")
        ).hexdigest()

        # Up to 10 digits pulled from the hash. A 64-character SHA-256
        # hex digest yields far more than 10 digit characters in
        # practice (roughly 10 of every 16 hex characters are digits),
        # but the filter is probabilistic, not guaranteed — pad to
        # exactly 10 with zfill BEFORE checking the leading digit, not
        # after. Doing it in the other order lets zfill's left-padding
        # reintroduce a leading zero that the check just removed, in
        # the rare case where fewer than 10 digit characters survived
        # the filter.
        digits = "".join(c for c in digest if c.isdigit())[:10]
        digits = digits.zfill(10)

        # Leading digit forced non-zero so the number reads as a
        # plausible account rather than something like "0123456789".
        if digits[0] == "0":
            digits = "1" + digits[1:]

        return VirtualAccount(
            account_number=digits,
            bank_name=_BANK_NAMES.get(country, "NovaBanq"),
            account_name=account_name,
            provider_ref=f"mock_{uuid.uuid4().hex}",
            currency=currency,
            country=country,
        )