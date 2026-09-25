from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Currency(StrEnum):
    NGN = "NGN"
    GHS = "GHS"
    KES = "KES"
    XOF = "XOF"
    ZAR = "ZAR"


class Country(StrEnum):
    NIGERIA = "NG"
    GHANA = "GH"
    KENYA = "KE"
    SENEGAL = "SN"
    IVORY_COAST = "CI"
    SOUTH_AFRICA = "ZA"


# Minor unit multipliers — how many minor units make one major unit.
# XOF has no minor unit (West African CFA franc is a zero-decimal currency).
CURRENCY_MINOR_UNITS: dict[Currency, int] = {
    Currency.NGN: 100,
    Currency.GHS: 100,
    Currency.KES: 100,
    Currency.XOF: 1,
    Currency.ZAR: 100,
}


# Country → ISO numeric prefix used in NovaBanq account numbers.
ACCOUNT_NUMBER_COUNTRY_PREFIX: dict[Country, str] = {
    Country.NIGERIA: "01",
    Country.GHANA: "02",
    Country.KENYA: "03",
    Country.SENEGAL: "04",
    Country.IVORY_COAST: "05",
    Country.SOUTH_AFRICA: "06",
}


# Country → default settlement currency. A user's currency is derived
# from their country at signup — the client never states one. This is
# not one-to-one: Senegal and Ivory Coast are both in the West African
# monetary union and both settle in XOF.
COUNTRY_CURRENCY: dict[Country, Currency] = {
    Country.NIGERIA: Currency.NGN,
    Country.GHANA: Currency.GHS,
    Country.KENYA: Currency.KES,
    Country.SENEGAL: Currency.XOF,
    Country.IVORY_COAST: Currency.XOF,
    Country.SOUTH_AFRICA: Currency.ZAR,
}


# Country → lowercase suffix appended to the user's @tag.
# The suffix is derived from the profile country, never from user input.
# Example: a user in Nigeria who claims "david" is stored as "david.ng".
COUNTRY_TAG_SUFFIX: dict[Country, str] = {
    Country.NIGERIA: "ng",
    Country.GHANA: "gh",
    Country.KENYA: "ke",
    Country.SENEGAL: "sn",
    Country.IVORY_COAST: "ci",
    Country.SOUTH_AFRICA: "za",
}


class FirestoreCollection(StrEnum):
    USERS = "users"
    TAGS = "tags"
    ACCOUNT_NUMBERS = "account_numbers"
    ACCOUNTS = "accounts"
    SYSTEM_ACCOUNTS = "system_accounts"
    TRANSACTIONS = "transactions"
    LEDGER_ENTRIES = "ledger_entries"
    CORRIDORS = "corridors"
    CURRENCIES = "currencies"
    FUNDING_RECORDS = "funding_records"
    IDEMPOTENCY_KEYS = "idempotency_keys"
    OTP_CODES = "otp_codes"
    IDENTITY_VERIFICATIONS = "identity_verifications"


class OtpPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"


class AccountType(StrEnum):
    """Distinguishes user wallets from platform clearing accounts.

    USER   — a real person's wallet. Debits require sufficient balance;
             the balance never goes negative.
    SYSTEM — a platform-owned clearing account (FX bridge, fee
             collector). Not tied to any user. Balances may go negative
             because these accounts track what the platform owes or
             holds pending settlement.
    """

    USER = "USER"
    SYSTEM = "SYSTEM"


class SystemAccountPurpose(StrEnum):
    """Purpose of a system account. Combined with a currency code by
    ``system_account_id`` to form the document id, e.g. ``fx_GHS``."""

    FX_BRIDGE = "fx"
    FEE_COLLECTOR = "fee"


class EntryDirection(StrEnum):
    """Direction of a single ledger entry.

    DEBIT  — money leaves an account. Balance decreases.
    CREDIT — money enters an account. Balance increases.
    """

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class TransactionType(StrEnum):
    """High-level category of a money-movement operation."""

    TRANSFER = "TRANSFER"
    FUNDING = "FUNDING"
    WITHDRAWAL = "WITHDRAWAL"
    REVERSAL = "REVERSAL"


class TransactionStatus(StrEnum):
    """Lifecycle state of a transaction.

    The ledger writes transactions in a single atomic commit: the
    transaction document and its ledger entries are written together,
    or not at all. In practice every persisted ``TransactionDocument``
    has ``status=SETTLED``; a transaction that fails to balance or
    would leave a user account negative aborts before anything is
    written.

    PENDING and FAILED remain valid values, reserved for a possible
    future two-phase flow (write PENDING first, settle or fail it in a
    second write) that would let a failed attempt leave a persisted
    audit trail. That flow is not implemented today.
    """

    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class RateSource(StrEnum):
    """Where a corridor's current rate came from.

    MANUAL     — set by an admin or seeded at deploy time. Never
                 refreshed by the service; used for the demo corridors
                 so the pitch cannot break on a third-party outage.
    FXRATESAPI — fetched from the live FX provider and cached with a
                 ``fetched_at`` timestamp. Refreshed on the next request
                 once the cache window expires.
    """

    MANUAL = "manual"
    FXRATESAPI = "fxratesapi"


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    TAG_TAKEN = "TAG_TAKEN"
    TAG_INVALID = "TAG_INVALID"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    RECIPIENT_NOT_FOUND = "RECIPIENT_NOT_FOUND"
    SELF_TRANSFER = "SELF_TRANSFER"
    CORRIDOR_UNSUPPORTED = "CORRIDOR_UNSUPPORTED"
    DUPLICATE_TRANSFER = "DUPLICATE_TRANSFER"
    RATE_EXPIRED = "RATE_EXPIRED"
    RATE_UNAVAILABLE = "RATE_UNAVAILABLE"
    FX_PROVIDER_UNAVAILABLE = "FX_PROVIDER_UNAVAILABLE"
    AMOUNT_INVALID = "AMOUNT_INVALID"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_TOO_MANY_ATTEMPTS = "OTP_TOO_MANY_ATTEMPTS"
    OTP_RESEND_TOO_SOON = "OTP_RESEND_TOO_SOON"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    EMAIL_DELIVERY_FAILED = "EMAIL_DELIVERY_FAILED"
    PHONE_MISMATCH = "PHONE_MISMATCH"
    PIN_ALREADY_SET = "PIN_ALREADY_SET"
    PIN_INVALID = "PIN_INVALID"
    PIN_LOCKED = "PIN_LOCKED"
    IDENTITY_VERIFICATION_FAILED = "IDENTITY_VERIFICATION_FAILED"
    IDENTITY_ALREADY_VERIFIED = "IDENTITY_ALREADY_VERIFIED"
    IDENTITY_PROVIDER_UNAVAILABLE = "IDENTITY_PROVIDER_UNAVAILABLE"
    LEDGER_ENTRY_INVALID = "LEDGER_ENTRY_INVALID"
    LEDGER_PRECONDITION_VIOLATED = "LEDGER_PRECONDITION_VIOLATED"
    LEDGER_UNBALANCED = "LEDGER_UNBALANCED"
    TRANSACTION_NOT_FOUND = "TRANSACTION_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# System account ids
# ---------------------------------------------------------------------------

def system_account_id(
    purpose: SystemAccountPurpose,
    currency: Currency,
) -> str:
    """Return the canonical document id for a system account.

    The single source of truth for system account ids. Never construct
    these strings manually — always go through this function so a typo
    cannot silently route a ledger operation to a missing account.

    Format is ``<purpose>_<currency>`` with a lowercase purpose and an
    uppercase currency: ``fx_GHS``, ``fee_NGN``.

    Args:
        purpose: The account's purpose (FX bridge, fee collector).
        currency: The currency the account holds.

    Returns:
        A document id, e.g. ``"fx_GHS"`` or ``"fee_NGN"``.
    """
    return f"{purpose.value}_{currency.value}"


def parse_system_account_id(
    account_id: str,
) -> tuple[SystemAccountPurpose, Currency]:
    """Inverse of ``system_account_id``.

    Splits a system account id back into its purpose and currency, with
    validation against the known enum members. Used by the ledger's
    instruction validator to reject malformed system account ids at
    construction time rather than letting a bad id reach Firestore.

    Args:
        account_id: A string like ``"fx_GHS"``.

    Returns:
        A ``(purpose, currency)`` tuple.

    Raises:
        ValueError: If the id is not of the form ``<purpose>_<currency>``
            or either part is not a recognised enum member.
    """
    parts = account_id.split("_", 1)
    if len(parts) != 2:
        raise ValueError(
            f"System account id must be '<purpose>_<currency>', got "
            f"{account_id!r}."
        )

    purpose_str, currency_str = parts
    try:
        purpose = SystemAccountPurpose(purpose_str)
    except ValueError as exc:
        raise ValueError(
            f"Unknown system account purpose {purpose_str!r} in "
            f"{account_id!r}."
        ) from exc

    try:
        currency = Currency(currency_str)
    except ValueError as exc:
        raise ValueError(
            f"Unknown currency {currency_str!r} in {account_id!r}."
        ) from exc

    return purpose, currency


# Account number format: 2-digit country prefix + 8 random digits = 10 numeric digits.
# Matches NUBAN length. Replaced by the payment provider's NUBAN when real
# virtual accounts are issued via Flutterwave.
ACCOUNT_NUMBER_COUNTRY_DIGITS = 2
ACCOUNT_NUMBER_RANDOM_DIGITS = 8
ACCOUNT_NUMBER_MAX_RETRIES = 5

# Tag rules.
TAG_MIN_LENGTH = 3
TAG_MAX_LENGTH = 20
TAG_ALLOWED_PATTERN = r"^[a-z0-9_]+$"
TAG_SUFFIX_SEPARATOR = "."

# OTP rules.
OTP_CODE_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 10

# PIN rules.
PIN_LENGTH = 5
PIN_MAX_ATTEMPTS = 5
PIN_LOCKOUT_MINUTES = 20

# Identity verification rules.
IDENTITY_BVN_LENGTH = 11
IDENTITY_FACE_MIN_CONFIDENCE = 0.70

# Ledger rules.
# Maximum number of instructions (legs) a single ledger operation may
# contain. This is a conservative business rule, not the Firestore
# document limit (which is 500). A GHS→NGN transfer is 5 legs; 20
# leaves room for multi-hop corridors without letting a caller
# construct a pathological instruction set that would be slow and
# hard to reason about.
LEDGER_MAX_LEGS_PER_TRANSACTION = 20
# Scale factor for storing the FX rate as an integer. A rate of 116.5
# is stored as 116_500_000 (116.5 × 10^6). Six decimal places is
# enough precision for every African corridor and keeps the ledger a
# pure-integer system.
LEDGER_RATE_SCALE = 1_000_000

# Transfer rules.
# Enforced by the transfers, funding, and withdrawal services — NOT by
# the ledger. The ledger's instruction validator does not enforce a
# minimum; that is business policy belonging to the calling service,
# per the ledger's documented scope.
#
# Minimum amount for any outbound transfer, expressed in minor units
# of the sender's currency. Prevents zero-value transfers and dust
# amounts that cost more to process than they move. Tune per corridor
# when real fees are known.
TRANSFER_MIN_AMOUNT_MINOR = 100

# FX rules.
# A rate is considered fresh for this long. Requests within the window
# are served from Firestore without hitting FxRatesAPI.
RATE_CACHE_SECONDS = 300
# After this long, even a cached rate is too old to trust. If the live
# provider is unreachable past this point, the corridor raises
# RATE_UNAVAILABLE rather than pricing a transfer on a stale value.
RATE_STALE_HARD_LIMIT_SECONDS = 3600
# How long a quoted rate is locked for the frontend between the quote
# screen and the confirm screen.
RATE_LOCK_SECONDS = 45

# HTTP status codes used across the API.
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_429_TOO_MANY_REQUESTS = 429
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_502_BAD_GATEWAY = 502