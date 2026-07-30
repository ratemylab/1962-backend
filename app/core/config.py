from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


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
    def database_url(self) -> str:
        """Synchronous database URL, retained for existing consumers such as Alembic."""
        return self._database_url("postgresql+psycopg")

    @property
    def database_url_async(self) -> str:
        """Asynchronous database URL used by the application session factory."""
        return self._database_url("postgresql+asyncpg")


settings = Settings()
