"""Guards the claim that the mock validates inputs exactly like the real adapter.

The mock's validators are copies of ``african_kyc.py``'s. If someone
tightens one and forgets the other, a test can pass under the mock and
then fail in production. These tests compare outcomes, including error
messages, so any drift fails here.

They also cover the mock's own behaviour — sentinel BVNs, determinism,
and PII scoping — so the rest of the codebase can rely on the mock
producing predictable results.
"""

import pytest

from app.infra.identity.african_kyc import AfricanKYCProvider as Real
from app.infra.identity.base import VerificationStatus
from app.infra.identity.mock import MockIdentityProvider as Mock

_RAW_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

BVNS = [
    "12345678901",
    "00000000000",
    "١٢٣٤٥٦٧٨٩٠١",  # Arabic-Indic digits
    "²" * 11,  # superscript digits: isdigit() is True
    "1234567890",
    "123456789012",
    "1234567890a",
    " 12345678901",
    "",
    None,
    12345678901,
]

IMAGES = [
    "https://example.com/selfie.jpg",
    _RAW_B64,
    "data:image/png;base64," + _RAW_B64,
    _RAW_B64[:60] + "\n" + _RAW_B64[60:],
    "http://example.com/selfie.jpg",
    "HTTPS://example.com/selfie.jpg",
    "file:///etc/passwd",
    "ftp://host/x",
    "javascript:alert(1)",
    "hello",
    "   ",
    "",
    "data:image/png,abc",
    "data:image/png;base64,",
    "A" * 9_000_000,
    None,
    5,
]


def _outcome(fn, value):
    """Return either 'ok' or the exception type and message as a string."""
    try:
        fn(value)
    except Exception as exc:  # noqa: BLE001 - we compare whatever is raised
        return f"{type(exc).__name__}: {exc}"
    return "ok"


def _id(value):
    """Return a printable, ASCII-safe pytest id for any input value.

    Non-ASCII values (Arabic-Indic digits, superscripts) are escaped so
    the id renders on any terminal, including Windows PowerShell with a
    legacy code page.
    """
    raw = repr(value)[:30]
    return raw.encode("ascii", "backslashreplace").decode("ascii")


# ---------------------------------------------------------------------------
# Validator parity — mock vs real
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bvn", BVNS, ids=_id)
def test_bvn_validation_matches_real_adapter(bvn):
    """The mock and real BVN validators must accept and reject identically."""
    assert _outcome(Mock._validate_bvn, bvn) == _outcome(Real._validate_bvn, bvn)


@pytest.mark.parametrize("image", IMAGES, ids=_id)
def test_image_validation_matches_real_adapter(image):
    """The mock and real image validators must accept and reject identically."""
    assert _outcome(Mock._validate_image, image) == _outcome(
        Real._validate_image, image
    )


# ---------------------------------------------------------------------------
# Mock verdict behaviour
# ---------------------------------------------------------------------------

_VALID_IMAGE = "data:image/png;base64," + _RAW_B64


def test_mock_sentinel_bvns_return_expected_statuses():
    """Each sentinel BVN must map to its documented verification status."""
    provider = Mock()

    assert (
        provider.verify_bvn_with_face("00000000000", _VALID_IMAGE).status
        is VerificationStatus.REJECTED
    )
    assert (
        provider.verify_bvn_with_face("99999999999", _VALID_IMAGE).status
        is VerificationStatus.WATCHLISTED
    )
    assert (
        provider.verify_bvn_with_face("11111111111", _VALID_IMAGE).status
        is VerificationStatus.NOT_FOUND
    )
    assert (
        provider.verify_bvn_with_face("12345678901", _VALID_IMAGE).status
        is VerificationStatus.VERIFIED
    )


def test_mock_is_deterministic():
    """The same BVN must always produce the same person and reference."""
    provider = Mock()

    first = provider.verify_bvn_with_face("12345678901", _VALID_IMAGE)
    second = provider.verify_bvn_with_face("12345678901", _VALID_IMAGE)

    assert first.person == second.person
    assert first.confidence == second.confidence
    assert first.provider_reference == second.provider_reference
    assert first.status == second.status


def test_mock_person_present_only_on_verified():
    """PII must never attach to a non-VERIFIED result."""
    provider = Mock()

    for sentinel in ("00000000000", "99999999999", "11111111111"):
        result = provider.verify_bvn_with_face(sentinel, _VALID_IMAGE)
        assert result.person is None, (
            f"PII leaked on status={result.status} for BVN {sentinel}"
        )

    verified = provider.verify_bvn_with_face("12345678901", _VALID_IMAGE)
    assert verified.person is not None


def test_mock_verifies_with_https_and_raw_base64_images():
    """The mock must accept every image form the real adapter accepts."""
    provider = Mock()

    for image in (
        "https://example.com/selfie.jpg",
        _RAW_B64,
        "data:image/png;base64," + _RAW_B64,
    ):
        result = provider.verify_bvn_with_face("12345678901", image)
        assert result.status is VerificationStatus.VERIFIED


def test_mock_rejects_bad_bvn_before_generating_a_verdict():
    """Malformed input must raise ValueError, not return a mock verdict."""
    provider = Mock()

    with pytest.raises(ValueError):
        provider.verify_bvn_with_face("123", _VALID_IMAGE)
    with pytest.raises(ValueError):
        provider.verify_bvn_with_face("١٢٣٤٥٦٧٨٩٠١", _VALID_IMAGE)
    with pytest.raises(ValueError):
        provider.verify_bvn_with_face("12345678901", "file:///etc/passwd")
    with pytest.raises(ValueError):
        provider.verify_bvn_with_face("12345678901", "")


def test_mock_national_id_not_implemented():
    """The mock must signal that national ID verification is unsupported."""
    provider = Mock()

    with pytest.raises(NotImplementedError):
        provider.verify_national_id(
            country="GH",
            id_number="GHA-123456789-0",
            image=_VALID_IMAGE,
        )