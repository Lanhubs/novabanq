from typing import Any

from app.core.constants import ErrorCode


class NovaBanqError(Exception):
    """Base exception for all application-level errors.

    Every custom exception carries an error code, a human-readable message,
    and an HTTP status so the exception handler can serialize it uniformly.
    """

    status_code: int = 500
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.code = code or self.__class__.code
        self.details = details or {}
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Authentication & authorization
# ---------------------------------------------------------------------------

class AuthenticationError(NovaBanqError):
    status_code = 401
    code = ErrorCode.AUTH_INVALID
    message = "Authentication failed."


class MissingTokenError(AuthenticationError):
    code = ErrorCode.AUTH_REQUIRED
    message = "Authorization header is missing or malformed."


class InvalidTokenError(AuthenticationError):
    code = ErrorCode.AUTH_INVALID
    message = "The provided token is invalid or has expired."


# ---------------------------------------------------------------------------
# Users & identity
# ---------------------------------------------------------------------------

class UserNotFoundError(NovaBanqError):
    status_code = 404
    code = ErrorCode.USER_NOT_FOUND
    message = "User profile not found."


class UserAlreadyExistsError(NovaBanqError):
    status_code = 409
    code = ErrorCode.USER_ALREADY_EXISTS
    message = "A user with this identity already exists."


class TagTakenError(NovaBanqError):
    status_code = 409
    code = ErrorCode.TAG_TAKEN
    message = "This @tag is already taken."


class TagInvalidError(NovaBanqError):
    status_code = 422
    code = ErrorCode.TAG_INVALID
    message = "The provided @tag does not meet the required format."


# ---------------------------------------------------------------------------
# Accounts & balances
# ---------------------------------------------------------------------------

class AccountNotFoundError(NovaBanqError):
    status_code = 404
    code = ErrorCode.ACCOUNT_NOT_FOUND
    message = "Account not found."


class InsufficientBalanceError(NovaBanqError):
    status_code = 422
    code = ErrorCode.INSUFFICIENT_BALANCE
    message = "Insufficient balance for this transaction."


# ---------------------------------------------------------------------------
# Transfers & payments
# ---------------------------------------------------------------------------

class RecipientNotFoundError(NovaBanqError):
    status_code = 404
    code = ErrorCode.RECIPIENT_NOT_FOUND
    message = "Recipient could not be found."


class SelfTransferError(NovaBanqError):
    status_code = 422
    code = ErrorCode.SELF_TRANSFER
    message = "You cannot send money to yourself."


class CorridorUnsupportedError(NovaBanqError):
    status_code = 422
    code = ErrorCode.CORRIDOR_UNSUPPORTED
    message = "This currency corridor is not currently supported."


class DuplicateTransferError(NovaBanqError):
    status_code = 409
    code = ErrorCode.DUPLICATE_TRANSFER
    message = "This transfer has already been processed."


class RateExpiredError(NovaBanqError):
    status_code = 422
    code = ErrorCode.RATE_EXPIRED
    message = "The quoted rate has expired. Please request a new quote."


class InvalidAmountError(NovaBanqError):
    status_code = 422
    code = ErrorCode.AMOUNT_INVALID
    message = "The provided amount is invalid."


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class ValidationError(NovaBanqError):
    status_code = 422
    code = ErrorCode.VALIDATION_ERROR
    message = "The request payload failed validation."


class InternalError(NovaBanqError):
    status_code = 500
    code = ErrorCode.INTERNAL_ERROR
    message = "An internal error occurred."