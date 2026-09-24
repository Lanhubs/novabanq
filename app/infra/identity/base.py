"""Identity verification provider interface.

Defines the contract every KYC provider adapter must satisfy. Feature
services depend only on this interface — never on a concrete provider.
Swapping providers is therefore a one-line change in the service, not a
refactor.

Design principles:
    * Return a normalized ``IdentityResult`` — never the provider's raw
      response. Callers must not know which provider is in use.
    * Separate "verification rejected" (a business outcome) from
      "provider failed" (an infrastructure error). The former returns a
      result; the latter raises ``IdentityProviderError``.
    * Keep the raw provider payload on the result so the feature layer
      can store it for audit and compliance.
    * Be narrow. Only the two capabilities NovaBanq actually uses are
      declared here. Adding a third is a deliberate decision.

Note: the concrete adapter is selected by a factory that lives in the
identity feature service, not in this module. This file defines only
the interface.
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VerificationStatus(StrEnum):
    """Outcome of an identity verification attempt.

    Distinguishing these states lets the frontend show different
    messages and lets the backend apply different policies.

        VERIFIED     The provider confirmed the identity and the face
                     matched.
        REJECTED     The check ran and failed: the face did not match,
                     or its ``confidence`` was below the acceptance
                     threshold. Callers that want to prompt a retry
                     should check ``status == REJECTED`` and inspect
                     ``confidence``.
        WATCHLISTED  The provider flagged the identity. Treat as a
                     hard reject; do not offer a retry.
        NOT_FOUND    The provider has no record for the supplied ID.
    """

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    WATCHLISTED = "WATCHLISTED"
    NOT_FOUND = "NOT_FOUND"


# ---------------------------------------------------------------------------
# Result data
# ---------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class VerifiedPerson:
    """Personal data returned by the provider for a successful lookup.

    All fields are optional because different providers return different
    subsets. Only ``first_name`` and ``last_name`` are reliably present
    for Nigerian BVN lookups.

    Values are passed through exactly as the provider returns them. In
    particular ``date_of_birth`` has no fixed format (providers have
    returned both ``"10-sep-2000"`` and ``"1999-12-21"``), so parse it
    defensively.

    The custom ``__repr__`` prevents accidental PII leakage when an
    instance ends up in a log line or traceback. The fields themselves
    remain accessible — only their string representation is redacted.
    """

    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    phone_number: str | None = None
    state_of_origin: str | None = None
    nationality: str | None = None

    def __repr__(self) -> str:
        return "VerifiedPerson(<redacted>)"


@dataclass(frozen=True, repr=False)
class IdentityResult:
    """Normalized outcome of an identity verification.

    Attributes:
        status: The verification outcome. Callers must switch on this,
            not on a boolean. Coerced to ``VerificationStatus`` on
            construction; an invalid value raises ``ValueError``.
        confidence: Face match confidence between 0.0 and 1.0
            (enforced), or None if the provider did not return one.
        person: The identified person's data. Populated only when
            ``status`` is ``VERIFIED``. Adapters leave it ``None`` for
            every other status so a failed face check never hands back
            the ID holder's details; the full payload stays in ``raw``.
        provider: Short label identifying which provider produced this
            result (e.g. "african_kyc", "mock"). For audit only.
        provider_reference: The provider's own reference id for this
            verification, useful when raising disputes or support
            tickets. For audit only.
        raw: The unmodified provider response, stored for audit. Never
            log this. Never return it to the client. Excluded from
            equality and hashing so two results with different raw
            payloads can still compare equal on their business fields.
            ``frozen`` is shallow: the dict itself is still mutable, so
            treat it as read-only.

    Construction raises ``TypeError`` for a non-numeric confidence and
    ``ValueError`` for an invalid status or an out-of-range confidence,
    so adapter bugs surface immediately rather than in a later branch.

    The custom ``__repr__`` prevents accidental PII leakage when an
    instance ends up in a log line or traceback.
    """

    status: VerificationStatus
    confidence: float | None = None
    person: VerifiedPerson | None = None
    provider: str = "unknown"
    provider_reference: str | None = None
    raw: dict[str, Any] = field(
        default_factory=dict,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        # Coerce so a plain "VERIFIED" string becomes the enum member and
        # junk fails here instead of later in a repr or an if-chain.
        object.__setattr__(self, "status", VerificationStatus(self.status))

        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                self.confidence, (int, float)
            ):
                raise TypeError(
                    "confidence must be a number or None, got "
                    f"{type(self.confidence).__name__}"
                )
            # The `not 0.0 <= x <= 1.0` form also rejects NaN.
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError(
                    f"confidence must be within [0.0, 1.0], got "
                    f"{self.confidence!r}"
                )

    def __repr__(self) -> str:
        return (
            f"IdentityResult(status={self.status.value!r}, "
            f"confidence={self.confidence!r}, "
            f"provider={self.provider!r}, "
            f"provider_reference={self.provider_reference!r}, "
            f"person=<redacted>, raw=<redacted>)"
        )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def _rebuild_provider_error(
    cls: type,
    message: str,
    provider: str,
    cause: Exception | None,
) -> "IdentityProviderError":
    """Reconstruct an ``IdentityProviderError`` after pickling.

    Pickle and ``copy`` rebuild exceptions from ``self.args``, which
    would lose the ``provider`` and ``cause`` attributes and re-prefix
    the message with the default provider. This helper restores the
    original arguments so round-trips preserve the error's identity.
    """
    return cls(message, provider=provider, cause=cause)


class IdentityProviderError(Exception):
    """Raised when the identity provider itself fails.

    This is an infrastructure error, not a verification rejection.
    Callers should surface it as ``IDENTITY_PROVIDER_UNAVAILABLE`` and
    let the user retry later. Common causes:
        * Network timeout or connection failure.
        * Provider returned a non-2xx HTTP status, including 401/403
          (invalid or expired credentials) and 429 (rate limiting).
        * Provider reported it cannot complete the request (maintenance,
          exhausted account balance).
        * Provider returned a payload the adapter cannot interpret
          (non-JSON, missing fields, unrecognised codes or values).

    Some causes (bad credentials, an empty account balance) will not
    clear on retry and need attention from your team; adapters log
    those at error level.

    Args:
        message: Human-readable description for logs.
        provider: Which provider failed (for logs).
        cause: The underlying exception, if any. Chained to
            ``__cause__`` so tracebacks show the full picture.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.provider = provider
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
        super().__init__(f"[{provider}] {message}")

    def __reduce__(self):
        return (
            _rebuild_provider_error,
            (type(self), self.message, self.provider, self.cause),
        )


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class IdentityProvider(ABC):
    """Interface every KYC provider adapter must implement.

    Concrete adapters live alongside this file (e.g. ``african_kyc.py``,
    ``mock.py``). Feature services obtain an instance from a factory
    function in the identity feature module and never construct
    adapters directly.

    Implementations must:
        * Validate inputs before calling the provider. Images must be
          an HTTPS URL, a base64 data URI, or raw base64; any other URL
          scheme is rejected with ``ValueError``.
        * Normalize the response into an ``IdentityResult``.
        * Raise ``IdentityProviderError`` on infrastructure failure and
          on any response they cannot interpret. Never map those to
          ``REJECTED``.
        * Never raise on a verification *rejection* — return a result
          with status ``REJECTED``, ``WATCHLISTED``, or ``NOT_FOUND``.
        * Populate ``IdentityResult.person`` only for ``VERIFIED``.
        * Never log personally identifiable information (BVN, image,
          names, the ``raw`` payload). The ``raw`` field is for
          storage, not for logs.
        * Set a distinctive ``name`` class attribute. Concrete
          subclasses that leave it as ``"unknown"`` fail at class
          creation (import) time.
    """

    # Short label used in logs, audit records, and error messages.
    # Concrete subclasses must override this.
    name: ClassVar[str] = "unknown"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # isabstract() copes with being called mid-class-creation, so
        # abstract intermediate classes may omit `name`.
        if not inspect.isabstract(cls) and cls.name == "unknown":
            raise TypeError(
                f"{cls.__name__} must define a provider `name` "
                "(e.g. name = \"african_kyc\")."
            )

    @abstractmethod
    def verify_bvn_with_face(self, bvn: str, image: str) -> IdentityResult:
        """Verify a BVN alongside a facial image.

        The provider cross-references the BVN record against the
        supplied image. A successful call returns the verified person's
        data plus a face-match confidence score.

        Args:
            bvn: 11-digit Bank Verification Number.
            image: Face image as an HTTPS URL, a base64 data URI, or
                raw base64. Other URL schemes (``http:``, ``file:``,
                ...) are rejected.

        Returns:
            An ``IdentityResult`` with status ``VERIFIED``,
            ``REJECTED``, ``WATCHLISTED``, or ``NOT_FOUND``. ``person``
            is set only when the status is ``VERIFIED``.

        Raises:
            IdentityProviderError: On network, auth, rate-limit or
                provider-side failure, or an uninterpretable response.
            ValueError: If the BVN or image is malformed before the
                provider is even contacted.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_national_id(
        self,
        country: str,
        id_number: str,
        image: str,
    ) -> IdentityResult:
        """Verify a national ID alongside a facial image.

        Used for countries outside Nigeria (Ghana Card, Kenya National
        ID, Senegal Biometric ID, etc). The provider routes to the
        correct national database based on ``country``.

        Args:
            country: Two-letter ISO country code (e.g. "GH", "KE").
            id_number: The national ID number.
            image: Face image as an HTTPS URL, a base64 data URI, or
                raw base64. Other URL schemes are rejected.

        Returns:
            An ``IdentityResult``; ``person`` is set only when the
            status is ``VERIFIED``.

        Raises:
            IdentityProviderError: On provider-side failure or an
                uninterpretable response.
            ValueError: If inputs are malformed.
            NotImplementedError: If the provider does not yet support
                the requested country.
        """
        raise NotImplementedError