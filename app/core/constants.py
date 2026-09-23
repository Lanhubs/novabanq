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
CURRENCY_MINOR_UNITS: dict[str, int] = {
    Currency.NGN: 100,
    Currency.GHS: 100,
    Currency.KES: 100,
    Currency.XOF: 1,
    Currency.ZAR: 100,
}


# Country → ISO numeric prefix used in NovaBanq account numbers.
ACCOUNT_NUMBER_COUNTRY_PREFIX: dict[str, str] = {
    Country.NIGERIA: "01",
    Country.GHANA: "02",
    Country.KENYA: "03",
    Country.SENEGAL: "04",
    Country.IVORY_COAST: "05",
    Country.SOUTH_AFRICA: "06",
}


class FirestoreCollection(StrEnum):
    USERS = "users"
    TAGS = "tags"
    ACCOUNT_NUMBERS = "account_numbers"
    ACCOUNTS = "accounts"
    TRANSACTIONS = "transactions"
    LEDGER_ENTRIES = "ledger_entries"
    CORRIDORS = "corridors"
    CURRENCIES = "currencies"
    FUNDING_RECORDS = "funding_records"
    IDEMPOTENCY_KEYS = "idempotency_keys"
    OTP_CODES = "otp_codes"


class OtpPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"


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
    AMOUNT_INVALID = "AMOUNT_INVALID"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_TOO_MANY_ATTEMPTS = "OTP_TOO_MANY_ATTEMPTS"
    OTP_RESEND_TOO_SOON = "OTP_RESEND_TOO_SOON"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    EMAIL_DELIVERY_FAILED = "EMAIL_DELIVERY_FAILED"
    PIN_ALREADY_SET = "PIN_ALREADY_SET"
    PIN_INVALID = "PIN_INVALID"
    PIN_LOCKED = "PIN_LOCKED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Account number format: NB + 2-digit country + 8 random digits.
ACCOUNT_NUMBER_PREFIX = "NB"
ACCOUNT_NUMBER_RANDOM_DIGITS = 8
ACCOUNT_NUMBER_MAX_RETRIES = 5

# Tag rules.
TAG_MIN_LENGTH = 3
TAG_MAX_LENGTH = 20
TAG_ALLOWED_PATTERN = r"^[a-z0-9_]+$"

# OTP rules.
OTP_CODE_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 10

# PIN rules.
PIN_LENGTH = 5
PIN_MAX_ATTEMPTS = 5
PIN_LOCKOUT_MINUTES = 20

# FX rate validity window (seconds) — rate locks for the frontend.
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