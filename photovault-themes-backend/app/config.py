"""Settings, read from environment variables (or a .env file). See .env.example."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (SQLAlchemy URL). Postgres in production; tests use SQLite.
    database_url: str = "postgresql+psycopg://themes:themes@localhost:5432/themes"

    # Public read API. Same paths as the old backend, so the app only swaps its base URL.
    public_prefix: str = "/api/locker-theme/public"

    # Admin panel login and session cookie.
    admin_username: str
    admin_password: str
    secret_key: str
    cookie_secure: bool = True  # set false only for local http testing

    # Where theme files live. "s3" = any S3-compatible bucket (AWS S3, Cloudflare R2,
    # DigitalOcean Spaces...) served through cdn_base_url; "local" = disk, for development.
    storage_backend: Literal["s3", "local"] = "s3"
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None  # leave empty for AWS S3
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    cdn_base_url: str = ""  # e.g. https://cdn.example.com (the app only accepts https links)

    local_media_dir: str = "media"
    public_base_url: str = "http://localhost:8000"

    max_upload_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
