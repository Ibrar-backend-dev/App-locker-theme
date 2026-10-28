"""Test setup: SQLite database and local file storage in a temp folder, set before the app loads."""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="themes-test-")
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    STORAGE_BACKEND="local",
    LOCAL_MEDIA_DIR=os.path.join(_tmp, "media"),
    PUBLIC_BASE_URL="https://themes.test",
    ADMIN_USERNAME="admin",
    ADMIN_PASSWORD="secret",
    SECRET_KEY="test-secret-key-test-secret-key-0123",
    COOKIE_SECURE="false",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app, base_url="https://themes.test") as c:  # runs startup (creates tables)
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()
