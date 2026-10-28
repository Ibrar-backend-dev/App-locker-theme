"""Settings, read from environment variables (or a .env file). See .env.example."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (SQLAlchemy URL). SQLite is the local default; PostgreSQL is supported.
    database_url: str = "sqlite:///./app.db"

    # Public read API. Same paths as the old backend, so the app only swaps its base URL.
    public_prefix: str = "/api/locker-theme/public"

    # Admin panel login and session cookie.
    admin_username: str
    admin_password: str
    secret_key: str
    cookie_secure: bool = True  # set false only for local http testing

    # Where theme files live. "s3" = any S3-compatible bucket served through a CDN;
    # "local" = disk, for development or when S3 credentials are unavailable.
    storage_backend: Literal["s3", "local"] = "s3"
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None  # leave empty for AWS S3
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    cdn_base_url: str = ""

    local_media_dir: str = "media"
    public_base_url: str = "http://localhost:8000"

    max_upload_mb: int = 50

    @field_validator("database_url", mode="before")
    @classmethod
    def default_database_url(cls, value: str | None) -> str:
        return value.strip() if value and value.strip() else "sqlite:///./app.db"

    @model_validator(mode="after")
    def use_local_storage_without_s3_credentials(self) -> "Settings":
        if self.storage_backend == "s3" and not all(
            (
                self.s3_bucket,
                self.s3_access_key_id,
                self.s3_secret_access_key,
                self.cdn_base_url,
            )
        ):
            self.storage_backend = "local"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
