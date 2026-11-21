"""Application configuration loaded from environment variables.

All secrets come from the environment (or a local, git-ignored .env file).
In production the application refuses to start with weak or missing secrets.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_MARKERS = ("change-me", "changeme", "example", "placeholder")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", Path(__file__).resolve().parents[2] / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    product_name: str = "FinSight"

    database_url: str = "sqlite:///./finsight_dev.db"

    # Signing key for access/refresh/MFA tokens. Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(64))"
    secret_key: str = Field(default="dev-only-insecure-secret-key-change-me-0123456789abcdef")
    # Fernet key for field-level encryption (MFA secrets, gateway credentials). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    field_encryption_key: str = Field(default="")

    access_token_minutes: int = 15
    refresh_token_days: int = 7
    mfa_token_minutes: int = 5

    cookie_secure: bool = True
    cookie_domain: str | None = None

    # Comma-separated. Only needed when the UI is served from a different origin.
    cors_origins: str = ""
    allowed_hosts: str = "localhost,127.0.0.1"

    # When false (default), a company can be created only on first run.
    allow_open_registration: bool = False

    max_failed_logins: int = 5
    lockout_minutes: int = 15

    @field_validator("cors_origins", "allowed_hosts")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.is_production:
            lowered = self.secret_key.lower()
            if len(self.secret_key) < 48 or any(m in lowered for m in _INSECURE_MARKERS):
                raise ValueError("SECRET_KEY must be a random value of at least 48 characters in production")
            if not self.field_encryption_key:
                raise ValueError("FIELD_ENCRYPTION_KEY is required in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("PostgreSQL is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
