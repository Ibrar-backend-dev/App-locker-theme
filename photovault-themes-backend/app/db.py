"""Database engine and session per request."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_url = get_settings().database_url
engine = create_engine(
    _url,
    pool_pre_ping=True,
    # SQLite (tests) is used from the test client's worker thread.
    connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
