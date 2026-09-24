"""Provider-free identity adapter for development and demos.

Returns deterministic verification results without contacting any
external service. Used when ``KYC_PROVIDER=mock``, which is the default
in development. Reasons to run with the mock:

    * Local development and manual testing without spending vendor
      sandbox credits.
    * Automated tests that must not depend on the network.
    * Demos in environments where the vendor is unreachable.
    * Building the identity flow before vendor credentials are approved.

The mock implements the same input validation as the real adapter
(``african_kyc.py``), so a caller cannot accidentally pass tests with
the mock and fail in production because of an input the mock tolerated.
The validators are copies, not shared code, so ``test_mock_parity.py``
compares them against the real adapter and must be kept green.

Deterministic behaviour:
    The same BVN always produces the same person and the same
    confidence. No randomness. Tests can assert exact values.

    Certain sentinel BVNs trigger specific statuses so the verdict
    paths can be exercised without turning off the mock:

        00000000000  -> REJECTED    (face did not match)
        99999999999  -> WATCHLISTED (provider flagged the record)
        11111111111  -> NOT_FOUND   (no record for this BVN)
        any other    -> VERIFIED

    Every sentinel is a valid 11-digit BVN, so they pass input
    validation and reach the verdict logic exactly as a real BVN would.

What the mock does not cover:
    * The provider-failure path. It never raises
      ``IdentityProviderError``, so code that handles an unavailable
      provider must be tested some other way.
    * The vendor payload shape. ``raw`` is a small opaque dict, not a
      copy of the vendor's response.

Safety:
    * Never run the mock with real BVNs. ``provider_reference`` and the
      generated person are derived from an unsalted SHA-256 of the BVN,
      so anyone who sees a reference can recover the BVN by brute force.
    * The mock returns VERIFIED for almost every BVN. It must never be
      reachable in production; the factory that selects the adapter
      refuses ``mock`` when ``APP_ENV=production``.
"""

import base64
import binascii
import hashlib
import logging
import re
from typing import Any, ClassVar

from app.core.constants import IDENTITY_BVN_LENGTH
from app.infra.identity.base import (
    IdentityProvider,
    IdentityResult,
    VerificationStatus,
    VerifiedPerson,
)

logger = logging.getLogger(__name__)

# Sentinel BVNs that trigger specific statuses. Everything else is
# VERIFIED.
_BVN_REJECTED = "00000000000"
_BVN_WATCHLISTED = "99999999999"
_BVN_NOT_FOUND = "11111111111"

# Fixed confidences. The VERIFIED value is above any reasonable
# acceptance threshold; the REJECTED value is below any reasonable one.
_MOCK_CONFIDENCE = 0.99
_MOCK_REJECTED_CONFIDENCE = 0.12

# Image validation limits. Keep in sync with ``african_kyc.py``;
# ``test_mock_parity.py`` fails if they drift.
_MAX_IMAGE_CHARS = 8_000_000
_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Small, deterministic name pools. Indexed by hash so the same BVN
# always produces the same name. These are generic placeholder names —
# they do not represent real people.
_FIRST_NAMES = (
    "Ada",
    "Chidi",
    "Ngozi",
    "Emeka",
    "Funmi",
    "Tunde",
    "Amaka",
    "Kelechi",
)
_MIDDLE_NAMES = (
    "Chukwuemeka",
    "Ngozi",
    "Oluwaseun",
    "Ifeoma",
    "Adeyemi",
    "Chiamaka",
)
_LAST_NAMES = (
    "Okafor",
    "Adeyemi",
    "Balogun",
    "Eze",
    "Nwosu",
    "Adebayo",
    "Ibrahim",
    "Okonkwo",
)

# Nigerian states, used to make the mock payload realistic for
# non-sensitive display fields.
_STATES = (
    "Lagos",
    "Abuja FCT",
    "Rivers",
    "Kano",
    "Oyo",
    "Anambra",
    "Kaduna",
    "Enugu",
)

# Three-letter lowercase months, matching Prembly's documented sample
# date of birth ("10-sep-2000").
_MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)

# Real Nigerian mobile prefixes, so downstream phone validation is
# exercised with plausible 11-digit numbers.
_PHONE_PREFIXES = (
    "0701", "0802", "0803", "0806", "0810", "0813", "0901", "0903",
)


class MockIdentityProvider(IdentityProvider):
    """Deterministic, provider-free implementation of ``IdentityProvider``.

    Never raises ``IdentityProviderError`` — the mock is always
    available. Raises ``ValueError`` for malformed inputs, matching the
    real adapter's contract so callers can rely on the same exception
    behaviour regardless of which adapter is active.

    The ``is_usable_in_production`` class attribute is False so the
    factory in the identity feature service can refuse to select this
    adapter when ``APP_ENV=production``. That is a defense-in-depth
    measure, not the primary gate — the primary gate is the env var.
    """

    name = "mock"
    is_usable_in_production: ClassVar[bool] = False

    # ------------------------------------------------------------------
    # BVN + face
    # ------------------------------------------------------------------

    def verify_bvn_with_face(self, bvn: str, image: str) -> IdentityResult:
        """Return a deterministic verification result for the given BVN.

        Sentinel BVNs trigger specific non-VERIFIED statuses; any other
        valid BVN returns ``VERIFIED`` with generated person data.

        Raises:
            ValueError: If the BVN or image is malformed.
        """
        self._validate_bvn(bvn)
        self._validate_image(image)

        result = self._verdict(bvn)

        # Deliberately no BVN in the log line, masked or not: the
        # IdentityProvider contract says adapters never log it.
        logger.info(
            "Mock identity verification completed with status %s.",
            result.status.value,
        )
        return result

    # ------------------------------------------------------------------
    # National ID — not yet supported by the mock either, for parity
    # ------------------------------------------------------------------

    def verify_national_id(
        self,
        country: str,
        id_number: str,
        image: str,
    ) -> IdentityResult:
        """Not implemented for this adapter yet.

        Parity with the real adapter. When Ghana / Kenya / Senegal flows
        are added, both adapters implement this together.
        """
        raise NotImplementedError(
            "National ID verification is not yet supported by the mock "
            "identity adapter."
        )

    # ------------------------------------------------------------------
    # Result construction
    # ------------------------------------------------------------------

    def _verdict(self, bvn: str) -> IdentityResult:
        """Map a validated BVN to its deterministic result."""
        if bvn == _BVN_REJECTED:
            return self._result(
                status=VerificationStatus.REJECTED,
                bvn=bvn,
                confidence=_MOCK_REJECTED_CONFIDENCE,
            )
        if bvn == _BVN_WATCHLISTED:
            return self._result(
                status=VerificationStatus.WATCHLISTED,
                bvn=bvn,
                confidence=None,
            )
        if bvn == _BVN_NOT_FOUND:
            return self._result(
                status=VerificationStatus.NOT_FOUND,
                bvn=bvn,
                confidence=None,
            )
        return self._result(
            status=VerificationStatus.VERIFIED,
            bvn=bvn,
            confidence=_MOCK_CONFIDENCE,
        )

    def _result(
        self,
        *,
        status: VerificationStatus,
        bvn: str,
        confidence: float | None,
    ) -> IdentityResult:
        """Build an ``IdentityResult`` with deterministic mock data.

        ``person`` is generated only for ``VERIFIED``, matching the
        real adapter. That is guaranteed by ``IdentityResult`` itself —
        it raises ``ValueError`` if a person is set on any other status.
        """
        person = (
            self._build_person(bvn)
            if status is VerificationStatus.VERIFIED
            else None
        )

        # Deliberately minimal and opaque: this does not mimic the
        # vendor payload, so storage code must treat ``raw`` as
        # arbitrary JSON.
        raw: dict[str, Any] = {
            "mock": True,
            "status": status.value,
            "bvn_masked": self._mask_bvn(bvn),
        }
        if confidence is not None:
            raw["confidence"] = confidence

        return IdentityResult(
            status=status,
            confidence=confidence,
            person=person,
            provider=self.name,
            provider_reference=f"mock-{self._short_hash(bvn)}",
            raw=raw,
        )

    # ------------------------------------------------------------------
    # Deterministic person generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_person(bvn: str) -> VerifiedPerson:
        """Derive a stable fake person from the BVN.

        Uses SHA-256 of the BVN to index into fixed name pools. The
        mapping is stable across runs and processes: the same BVN
        always produces the same person.
        """
        digest = hashlib.sha256(bvn.encode("ascii")).digest()

        first = _FIRST_NAMES[digest[0] % len(_FIRST_NAMES)]
        middle = _MIDDLE_NAMES[digest[1] % len(_MIDDLE_NAMES)]
        last = _LAST_NAMES[digest[2] % len(_LAST_NAMES)]
        state = _STATES[digest[3] % len(_STATES)]

        # Date of birth in Prembly's documented sample format,
        # "dd-mon-yyyy" (e.g. "10-sep-2000"). Prembly has also returned
        # ISO dates ("1999-12-21"), so downstream parsing must handle
        # both; the mock only emits the first.
        day = 1 + (digest[4] % 28)
        month = _MONTHS[digest[5] % 12]
        year = 1980 + (digest[6] % 25)
        dob = f"{day:02d}-{month}-{year}"

        gender = "Male" if digest[7] % 2 == 0 else "Female"

        # 11-digit Nigerian mobile number. Mock numbers can coincide
        # with real subscribers, so never send SMS or calls to them.
        prefix = _PHONE_PREFIXES[digest[12] % len(_PHONE_PREFIXES)]
        suffix = int.from_bytes(digest[8:12], "big") % 10_000_000
        phone = f"{prefix}{suffix:07d}"

        return VerifiedPerson(
            first_name=first,
            middle_name=middle,
            last_name=last,
            date_of_birth=dob,
            gender=gender,
            phone_number=phone,
            state_of_origin=state,
            nationality="Nigeria",
        )

    # ------------------------------------------------------------------
    # Validation — matches the real adapter exactly
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_bvn(bvn: str) -> None:
        if (
            not isinstance(bvn, str)
            or not bvn.isascii()
            or not bvn.isdigit()
            or len(bvn) != IDENTITY_BVN_LENGTH
        ):
            raise ValueError(
                f"BVN must be exactly {IDENTITY_BVN_LENGTH} digits."
            )

    @staticmethod
    def _validate_image(image: str) -> None:
        """Accept the same image forms as the real adapter.

        Matching rules means a caller cannot pass tests under the mock
        with an input the real adapter would reject.
        """
        if not isinstance(image, str) or not image.strip():
            raise ValueError("A face image is required.")
        if len(image) > _MAX_IMAGE_CHARS:
            raise ValueError("Face image is too large.")

        if image.startswith("https://"):
            return

        if image.startswith("data:image/"):
            _, sep, payload = image.partition(";base64,")
            if not sep:
                raise ValueError("Face image data URI must be base64 encoded.")
        elif _URL_SCHEME_RE.match(image):
            raise ValueError("Face image URLs must use HTTPS.")
        else:
            payload = image

        compact = "".join(payload.split())
        if not compact:
            raise ValueError("A face image is required.")
        try:
            base64.b64decode(compact, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Face image is not valid base64.") from None

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_bvn(bvn: str) -> str:
        """Return a BVN with all but the last four digits masked.

        Used only for the stored ``raw`` payload, never for logs.
        """
        if len(bvn) <= 4:
            return "*" * len(bvn)
        return "*" * (len(bvn) - 4) + bvn[-4:]

    @staticmethod
    def _short_hash(value: str) -> str:
        """Return a short, stable hash suitable for a reference id."""
        return hashlib.sha256(value.encode("ascii")).hexdigest()[:12]