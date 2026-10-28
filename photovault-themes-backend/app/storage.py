"""Theme file storage: an S3-compatible bucket in production, the local disk in development."""

from functools import lru_cache
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.config import get_settings


class Storage(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def url(self, key: str | None) -> str | None: ...


def new_key(kind: str, filename: str | None) -> str:
    """Unique, unguessable bucket path, keeping the file extension: themes/<kind>/<hex>.<ext>."""
    suffix = Path(filename or "").suffix.lower()
    if not suffix[1:].isalnum() or len(suffix) > 6:
        suffix = ""
    return f"themes/{kind}/{uuid4().hex}{suffix}"


class S3Storage:
    def __init__(self) -> None:
        import boto3

        s = get_settings()
        self.bucket = s.s3_bucket
        self.cdn = s.cdn_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url or None,
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id or None,
            aws_secret_access_key=s.s3_secret_access_key or None,
        )

    def save(self, key: str, data: bytes, content_type: str) -> None:
        # Keys never change (new upload = new key), so the CDN can cache forever.
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key: str | None) -> str | None:
        return f"{self.cdn}/{key}" if key else None


class LocalStorage:
    def __init__(self) -> None:
        s = get_settings()
        self.root = Path(s.local_media_dir)
        self.base = s.public_base_url.rstrip("/")

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)

    def url(self, key: str | None) -> str | None:
        return f"{self.base}/media/{key}" if key else None


@lru_cache
def get_storage() -> Storage:
    return S3Storage() if get_settings().storage_backend == "s3" else LocalStorage()
