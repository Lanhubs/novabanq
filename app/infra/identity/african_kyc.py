"""African KYC provider adapter (Prembly IdentityPass — BVN + face).

Concrete ``IdentityProvider`` implementation that talks to an external
BVN + face verification service. The vendor's name is intentionally not
part of the class or module name — swapping vendors means replacing this
file, not renaming anything.

Endpoint contract (per docs.prembly.com, "BVN + (Face Validation)"):
    POST https://api.prembly.com/identitypass/verification/bvn_w_face
    Headers:
        app-id: <account app id>
        x-api-key: <account secret key>
        content-type: application/json
    Body:
        {"number": "<11-digit BVN>", "image": "<image URL or base64>"}

    NOTE: the docs page for this endpoint lists the path without the
    ``/identitypass`` prefix, while Prembly's API reference and sibling
    endpoints use it. If ``_BVN_FACE_PATH`` ever 404s, try the other one.

Verdicts are returned inside HTTP 200 as a top-level ``response_code``
(Prembly "Response Codes & Verification Status" page):
    "00"  success — inspect ``face_data`` for the face verdict
    "01"  record not found
    "02"  service unavailable, retry later      -> provider error
    "03"  insufficient wallet balance           -> provider error
    "07"  BVN blocked / watch-listed
Any non-2xx HTTP status is an infrastructure failure (400, 401, 403,
404, 422, 429, 5xx all mean "our request or the provider is broken", not
"the user failed verification").

Success payload shape consumed:
    response_code                    str    — see above
    data.watchListed                 "YES" | "NO" (older/newer docs also
                                     show true/false) — accepted case-
                                     insensitively, unknown values raise
    data.firstName / middleName / lastName / dateOfBirth / gender /
         phoneNumber1 / stateOfOrigin / nationality
    data.face_data.status            bool   — the face-match verdict
    data.face_data.confidence        float  — 0.0 to 1.0
    verification.reference           str    — provider reference id
      (``face_data`` is also accepted at the top level of the body, which
      is where older copies of the docs place it.)

The raw payload is returned inside ``IdentityResult.raw`` for storage
and audit. It is never logged and never sent to the client.
"""

import base64
import binascii
import logging
import math
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.constants import IDENTITY_BVN_LENGTH, IDENTITY_FACE_MIN_CONFIDENCE
from app.infra.identity.base import (
    IdentityProvider,
    IdentityProviderError,
    IdentityResult,
    VerificationStatus,
    VerifiedPerson,
)

logger = logging.getLogger(__name__)

_BVN_FACE_PATH = "/identitypass/verification/bvn_w_face"
_REQUEST_TIMEOUT_SECONDS = 20.0
_MAX_IMAGE_CHARS = 8_000_000  # assumption: tune to Prembly's image limits

# Top-level ``response_code`` values (returned inside HTTP 200).
_RESPONSE_CODE_SUCCESS = "00"
_RESPONSE_CODE_NOT_FOUND = "01"
_RESPONSE_CODE_UNAVAILABLE = "02"
_RESPONSE_CODE_INSUFFICIENT_BALANCE = "03"
_RESPONSE_CODE_WATCHLISTED = "07"

# ``watchListed`` is "YES"/"NO" in the docs and true/false elsewhere.
_TRUTHY_STRINGS = {"true", "1", "yes"}
_FALSY_STRINGS = {"false", "0", "no", ""}

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


class AfricanKYCProvider(IdentityProvider):
    """Concrete provider that verifies BVN + face via an external API.

    The base URL is read from ``settings.kyc_base_url`` so test
    environments can point at a sandbox without changing code.
    """

    name = "african_kyc"

    # ------------------------------------------------------------------
    # BVN + face
    # ------------------------------------------------------------------

    def verify_bvn_with_face(self, bvn: str, image: str) -> IdentityResult:
        """Verify a BVN against a face image.

        Raises:
            ValueError: If the BVN or image is malformed before any
                network call.
            IdentityProviderError: If the provider itself fails or
                returns a payload this adapter cannot interpret.
        """
        self._validate_bvn(bvn)
        self._validate_image(image)

        payload = {"number": bvn, "image": image}

        response = self._post(_BVN_FACE_PATH, payload)
        body = self._parse_json(response)

        return self._normalize_bvn_face_response(body)

    # ------------------------------------------------------------------
    # National ID (not yet supported by this adapter)
    # ------------------------------------------------------------------

    def verify_national_id(
        self,
        country: str,
        id_number: str,
        image: str,
    ) -> IdentityResult:
        """Not implemented for this adapter yet.

        Non-Nigerian countries route to a different vendor endpoint with
        a different payload shape. When that flow is needed, this method
        is implemented here — the interface does not change.
        """
        raise NotImplementedError(
            "National ID verification is not yet supported by the "
            "African KYC adapter."
        )

    # ------------------------------------------------------------------
    # Input validation
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
        """Accept an HTTPS URL, a base64 data URI, or raw base64.

        Prembly documents the image as "url (png, jpeg, base64)". Plain
        ``http://`` and other schemes (``file:``, ``ftp:`` ...) are
        rejected because the vendor fetches URLs on our behalf.
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
    # HTTP
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        """Send a POST to the vendor and translate failures.

        Every network-level problem, and every non-2xx status, becomes
        an ``IdentityProviderError``. Prembly reports verification
        verdicts inside HTTP 200, so a non-2xx never means "rejected".
        """
        url = f"{settings.kyc_base_url.rstrip('/')}{path}"
        headers = {
            "app-id": settings.kyc_app_id,
            "x-api-key": settings.kyc_api_key,
            "content-type": "application/json",
            "accept": "application/json",
        }

        try:
            with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            logger.error("KYC provider timed out on %s.", path)
            raise IdentityProviderError(
                "Identity provider timed out.",
                provider=self.name,
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("KYC provider request failed on %s.", path)
            raise IdentityProviderError(
                "Identity provider is unreachable.",
                provider=self.name,
                cause=exc,
            ) from exc

        if not response.is_success:
            logger.error(
                "KYC provider returned HTTP %s on %s.",
                response.status_code,
                path,
            )
            raise IdentityProviderError(
                f"Identity provider returned HTTP {response.status_code}.",
                provider=self.name,
            )

        return response

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        """Return the response as JSON, raising on malformed payloads."""
        try:
            data = response.json()
        except ValueError as exc:
            raise IdentityProviderError(
                "Identity provider returned a non-JSON payload.",
                provider=AfricanKYCProvider.name,
                cause=exc,
            ) from exc

        if not isinstance(data, dict):
            raise IdentityProviderError(
                "Identity provider returned an unexpected payload shape.",
                provider=AfricanKYCProvider.name,
            )
        return data

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalize_bvn_face_response(
        self,
        body: dict[str, Any],
    ) -> IdentityResult:
        """Map the vendor payload onto ``IdentityResult``.

        Order of checks: infrastructure codes (02/03) raise; then the
        code-level verdicts (07 watchlisted, 01 not found); then, for
        "00", the in-body watchlist flag, then the face verdict.
        """
        response_code = self._response_code(body)

        if response_code == _RESPONSE_CODE_UNAVAILABLE:
            logger.error("KYC provider reported service unavailable (02).")
            raise IdentityProviderError(
                "Identity provider is temporarily unavailable.",
                provider=self.name,
            )
        if response_code == _RESPONSE_CODE_INSUFFICIENT_BALANCE:
            logger.error(
                "KYC provider wallet balance is insufficient (03); "
                "top up the account."
            )
            raise IdentityProviderError(
                "Identity provider account has insufficient balance.",
                provider=self.name,
            )

        reference = self._provider_reference(body)

        # 1. Watchlisted at code level — hardest reject.
        if response_code == _RESPONSE_CODE_WATCHLISTED:
            return self._result(
                VerificationStatus.WATCHLISTED, body, reference=reference
            )

        # 2. Record not found.
        if response_code == _RESPONSE_CODE_NOT_FOUND:
            return self._result(
                VerificationStatus.NOT_FOUND, body, reference=reference
            )

        # 3. Anything other than "00" is a code we cannot interpret.
        if response_code != _RESPONSE_CODE_SUCCESS:
            raise IdentityProviderError(
                f"Identity provider returned unrecognised response_code "
                f"{response_code!r}.",
                provider=self.name,
            )

        data = self._section(body, "data")
        face_data = self._face_data(body, data)
        confidence = self._extract_confidence(face_data)

        # 4. Watchlist flag inside a "00" payload.
        if self._is_watchlisted(data):
            return self._result(
                VerificationStatus.WATCHLISTED,
                body,
                confidence=confidence,
                reference=reference,
            )

        # 5. Face verdict. Prembly's own boolean is authoritative; our
        #    minimum-confidence policy is applied on top of it.
        if (
            self._face_matched(face_data)
            and confidence is not None
            and confidence >= IDENTITY_FACE_MIN_CONFIDENCE
        ):
            return self._result(
                VerificationStatus.VERIFIED,
                body,
                confidence=confidence,
                person=self._extract_person(data),
                reference=reference,
            )

        # 6. Anything else is a plain rejection. No person data is
        #    returned unless the face matched (it stays in ``raw``).
        return self._result(
            VerificationStatus.REJECTED,
            body,
            confidence=confidence,
            reference=reference,
        )

    def _result(
        self,
        status: VerificationStatus,
        body: dict[str, Any],
        *,
        confidence: float | None = None,
        person: VerifiedPerson | None = None,
        reference: str | None = None,
    ) -> IdentityResult:
        return IdentityResult(
            status=status,
            confidence=confidence,
            person=person,
            provider=self.name,
            provider_reference=reference,
            raw=body,
        )

    @staticmethod
    def _response_code(body: dict[str, Any]) -> str:
        code = body.get("response_code")
        if isinstance(code, bool) or not isinstance(code, (str, int)):
            code = None
        elif isinstance(code, int):
            code = f"{code:02d}"
        else:
            code = code.strip()
        if not code:
            raise IdentityProviderError(
                "Identity provider response is missing a response_code.",
                provider=AfricanKYCProvider.name,
            )
        return code

    @staticmethod
    def _provider_reference(body: dict[str, Any]) -> str | None:
        """``verification.reference`` sits beside ``data``, not inside it."""
        verification = AfricanKYCProvider._section(body, "verification")
        reference = verification.get("reference")
        return str(reference) if reference else None

    @staticmethod
    def _face_data(body: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        """Locate ``face_data``: ``data.face_data`` first, then top level."""
        for parent in (data, body):
            value = parent.get("face_data")
            if value is None:
                continue
            if not isinstance(value, dict):
                raise IdentityProviderError(
                    "Identity provider returned an unexpected shape for "
                    "'face_data'.",
                    provider=AfricanKYCProvider.name,
                )
            return value
        raise IdentityProviderError(
            "Identity provider response is missing face_data.",
            provider=AfricanKYCProvider.name,
        )

    @staticmethod
    def _face_matched(face_data: dict[str, Any]) -> bool:
        value = face_data.get("status")
        if value is None:
            return False  # fail closed
        return AfricanKYCProvider._as_bool(value)

    @staticmethod
    def _extract_person(data: dict[str, Any]) -> VerifiedPerson | None:
        """Build a ``VerifiedPerson`` from the vendor payload.

        Returns None when the payload carries no identifying fields.
        """
        first = data.get("firstName")
        last = data.get("lastName")
        if not first and not last:
            return None

        return VerifiedPerson(
            first_name=first,
            middle_name=data.get("middleName"),
            last_name=last,
            date_of_birth=data.get("dateOfBirth"),
            gender=data.get("gender"),
            phone_number=data.get("phoneNumber1"),
            state_of_origin=data.get("stateOfOrigin"),
            nationality=data.get("nationality"),
        )

    @staticmethod
    def _extract_confidence(face_data: dict[str, Any]) -> float | None:
        """Return face match confidence (0.0-1.0), or None if absent.

        A non-numeric value is treated as absent. A numeric value that is
        non-finite or outside 0.0-1.0 means the vendor changed its scale
        or the payload is corrupt, so it raises instead of being trusted.
        """
        raw = face_data.get("confidence")
        if raw is None or isinstance(raw, bool):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise IdentityProviderError(
                "Identity provider returned an out-of-range face confidence.",
                provider=AfricanKYCProvider.name,
            )
        return value

    @staticmethod
    def _is_watchlisted(data: dict[str, Any]) -> bool:
        """Return True when the vendor flags the record as watchlisted."""
        value = data.get("watchListed")
        if value is None:
            return False
        return AfricanKYCProvider._as_bool(value)

    @staticmethod
    def _as_bool(value: Any) -> bool:
        """Strict bool parse; an unrecognised value is a payload error."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY_STRINGS:
                return True
            if normalized in _FALSY_STRINGS:
                return False
        raise IdentityProviderError(
            "Identity provider returned an unrecognised boolean value.",
            provider=AfricanKYCProvider.name,
        )

    @staticmethod
    def _section(parent: dict[str, Any], key: str) -> dict[str, Any]:
        """Return parent[key] as a dict; null -> {}; wrong type -> error."""
        value = parent.get(key)
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise IdentityProviderError(
                f"Identity provider returned an unexpected shape for '{key}'.",
                provider=AfricanKYCProvider.name,
            )
        return value