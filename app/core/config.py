import json
from base64 import b64decode
from binascii import Error as BinasciiError
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = "NovaBanq API"
    app_env: str = Field(default="development")
    app_version: str = "0.1.0"
    debug: bool = Field(default=False)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ------------------------------------------------------------------
    # Firebase credentials
    #
    # Three sources, resolved in priority order:
    #   1. FIREBASE_CREDENTIALS_BASE64  — base64-encoded service account JSON
    #   2. FIREBASE_CREDENTIALS_JSON    — raw service account JSON string
    #   3. FIREBASE_CREDENTIALS_PATH    — local file path (development only)
    # ------------------------------------------------------------------
    firebase_credentials_base64: str | None = Field(default=None)
    firebase_credentials_json: str | None = Field(default=None)
    firebase_credentials_path: Path | None = Field(
        default=Path("serviceAccountKey.json")
    )

    # ------------------------------------------------------------------
    # Brevo (transactional email delivery)
    # ------------------------------------------------------------------
    brevo_api_key: str | None = Field(default=None)
    brevo_sender_email: str | None = Field(default=None)
    brevo_sender_name: str = Field(default="NovaBanq")

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    demo_mode: bool = Field(default=True)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    # ------------------------------------------------------------------
    # Credential resolvers
    # ------------------------------------------------------------------
    def load_firebase_credentials(self) -> dict[str, Any]:
        """Resolve Firebase service account credentials.

        Returns the parsed service account dictionary, or raises
        RuntimeError if no valid credential source is available.
        """
        if self.firebase_credentials_base64:
            try:
                decoded = b64decode(self.firebase_credentials_base64).decode("utf-8")
                return json.loads(decoded)
            except (BinasciiError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "FIREBASE_CREDENTIALS_BASE64 is set but could not be decoded "
                    "into a valid service account JSON."
                ) from exc

        if self.firebase_credentials_json:
            try:
                return json.loads(self.firebase_credentials_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "FIREBASE_CREDENTIALS_JSON is set but is not valid JSON."
                ) from exc

        if self.firebase_credentials_path and self.firebase_credentials_path.exists():
            try:
                with self.firebase_credentials_path.open("r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Failed to read Firebase credentials from "
                    f"'{self.firebase_credentials_path}'."
                ) from exc

        raise RuntimeError(
            "No Firebase credentials available. Set FIREBASE_CREDENTIALS_BASE64 "
            "(recommended for production), FIREBASE_CREDENTIALS_JSON, or place a "
            "serviceAccountKey.json file at the project root for local development."
        )

    def require_brevo_config(self) -> tuple[str, str, str]:
        """Return (api_key, sender_email, sender_name) for Brevo.

        Raises RuntimeError if any required value is missing, so
        misconfiguration surfaces at the call site rather than as a
        confusing HTTP error mid-request.
        """
        api_key = self.brevo_api_key
        sender_email = self.brevo_sender_email
        sender_name = self.brevo_sender_name

        if not api_key:
            raise RuntimeError(
                "Brevo is not fully configured. Missing environment variable: "
                "BREVO_API_KEY"
            )
        if not sender_email:
            raise RuntimeError(
                "Brevo is not fully configured. Missing environment variable: "
                "BREVO_SENDER_EMAIL"
            )

        return api_key, sender_email, sender_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()