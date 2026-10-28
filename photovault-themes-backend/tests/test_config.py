from app.config import Settings


def test_missing_database_and_storage_credentials_use_local_defaults():
    settings = Settings(
        _env_file=None,
        admin_username="admin",
        admin_password="secret",
        secret_key="test-secret",
        database_url="",
        storage_backend="s3",
        s3_bucket="",
        s3_access_key_id="",
        s3_secret_access_key="",
        cdn_base_url="",
        local_media_dir="media",
    )

    assert settings.database_url == "sqlite:///./app.db"
    assert settings.storage_backend == "local"
    assert settings.local_media_dir == "media"
