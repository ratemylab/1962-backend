from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

from app.core.logging import logger

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Placeholder secret that keeps local development and tests runnable without a
# .env file. Any other value is treated as an operator-supplied secret.
DEFAULT_JWT_SECRET_KEY = "dev-only-insecure-jwt-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "Ticket Management Backend"
    app_version: str = "0.1.0"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins (comma-separated in CORS_ORIGINS)",
    )
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ticket_db"
    db_user: str = "postgres"
    db_password: str = "postgres"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    db_echo: bool = False
    audio_upload_path: Path = Path("uploads/audio")
    seed_clients_enabled: bool = True
    seed_client_token_bytes: int = 32
    client_token_hash_algorithm: str = "sha256"

    # Admin JWT authentication. Client APIs keep using static API tokens and are
    # unaffected by these settings.
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, gt=0)

    # Refresh tokens are opaque random strings rather than JWTs, so they are
    # revocable: only their hash is stored and it can be deleted on logout.
    refresh_token_expire_days: int = Field(default=7, gt=0)
    refresh_token_bytes: int = Field(default=32, gt=0)

    seed_admin_enabled: bool = True
    seed_admin_username: str = "admin"
    seed_admin_password: str = "Admin@123"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("cors_origins must be a comma-separated string or list")

    def _database_url(self, drivername: str) -> str:
        """Build a SQLAlchemy URL from the portable DB_* settings."""
        return URL.create(
            drivername=drivername,
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    @property
    def access_token_expires_in_seconds(self) -> int:
        """Access token lifetime in seconds, as reported by the login response."""
        return self.jwt_access_token_expire_minutes * 60

    @property
    def refresh_token_expires_in_seconds(self) -> int:
        """Refresh token lifetime in seconds, as reported by the login response."""
        return self.refresh_token_expire_days * 24 * 60 * 60

    @property
    def database_url(self) -> str:
        """Synchronous database URL, retained for existing consumers such as Alembic."""
        return self._database_url("postgresql+psycopg")

    @property
    def database_url_async(self) -> str:
        """Asynchronous database URL used by the application session factory."""
        return self._database_url("postgresql+asyncpg")


settings = Settings()

if settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY:
    logger.warning(
        "JWT_SECRET_KEY is unset; using the built-in development secret. "
        "Set JWT_SECRET_KEY before deploying, otherwise admin tokens are forgeable."
    )
