import json
from base64 import b64decode
from binascii import Error as BinasciiError
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Every field has a safe default. Nothing required is missing — if a
    deployment forgets to set something, either the feature is disabled
    (demo_mode, kyc_provider=mock) or the failure surfaces at the call
    site with a clear message via a ``require_*`` helper.

    The class is cached (see ``get_settings``) so this loads exactly
    once per process.
    """

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
    # KYC / Identity verification
    #
    # Vendor-neutral names — the concrete adapter is selected by
    # ``kyc_provider``. Switching vendors means changing this value and
    # the adapter file, never the rest of the codebase.
    #
    # ``kyc_environment`` is informational (logged at startup). Vendors
    # distinguish sandbox from live by the key prefix, not by the URL,
    # so the base URL stays the same in both modes.
    # ------------------------------------------------------------------
    kyc_provider: str = Field(default="mock")
    kyc_base_url: str = Field(default="https://api.prembly.com")
    kyc_app_id: str | None = Field(default=None)
    kyc_api_key: str | None = Field(default=None)
    kyc_environment: str = Field(default="sandbox")

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

    @property
    def uses_real_kyc(self) -> bool:
        """True when the app is configured to call a real KYC vendor.

        The mock adapter never needs credentials. Any other value of
        ``kyc_provider`` does. Callers use this to decide whether to
        call ``require_kyc_config()`` at startup.
        """
        return self.kyc_provider.strip().lower() != "mock"

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

    def require_kyc_config(self) -> tuple[str, str, str]:
        """Return (base_url, app_id, api_key) for the KYC vendor.

        Only called when ``kyc_provider`` is not ``"mock"``. Raises
        RuntimeError with a clear message if any value is missing so
        the app fails at startup, not on the first verification request.
        """
        base_url = self.kyc_base_url
        app_id = self.kyc_app_id
        api_key = self.kyc_api_key

        if not base_url:
            raise RuntimeError(
                "KYC is not fully configured. Missing environment variable: "
                "KYC_BASE_URL"
            )
        if not app_id:
            raise RuntimeError(
                "KYC is not fully configured. Missing environment variable: "
                "KYC_APP_ID"
            )
        if not api_key:
            raise RuntimeError(
                "KYC is not fully configured. Missing environment variable: "
                "KYC_API_KEY"
            )

        return base_url, app_id, api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()