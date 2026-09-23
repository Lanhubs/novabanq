"""OTP schemas.

Pydantic models for the OTP endpoints. These define the HTTP contract
the mobile client codes against. Because the OTP feature is small and
self-contained, only two request models and one response model are
required.

Naming convention:
    *Request  — validated on incoming HTTP calls.
    *Response — serialized on outgoing HTTP responses.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import OTP_CODE_LENGTH


class SendEmailOtpRequest(BaseModel):
    """Payload for requesting an email verification OTP.

    The destination email is taken from the authenticated Firebase user
    profile, never from the request body. This model exists so the
    endpoint can evolve (e.g. accept a locale hint) without breaking
    the contract later.
    """

    model_config = ConfigDict(extra="forbid")


class VerifyEmailOtpRequest(BaseModel):
    """Payload for verifying an email OTP."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: str = Field(
        ...,
        min_length=OTP_CODE_LENGTH,
        max_length=OTP_CODE_LENGTH,
        description=f"{OTP_CODE_LENGTH}-digit verification code.",
        examples=["482913"],
    )

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Verification code must contain only digits.")
        return value


class OtpIssuedResponse(BaseModel):
    """Returned after an OTP has been successfully issued."""

    model_config = ConfigDict(frozen=True)

    sent: bool = Field(
        ...,
        description="True if the OTP was accepted for delivery.",
    )
    expires_in_seconds: int = Field(
        ...,
        description="Number of seconds until the code expires.",
        examples=[600],
    )
    resend_available_in_seconds: int = Field(
        ...,
        description="Seconds the client must wait before requesting a new code.",
        examples=[10],
    )