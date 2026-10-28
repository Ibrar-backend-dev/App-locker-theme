"""Photo Vault & Locker themes backend: public read API for the app + admin panel."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import engine
from app.models import Base
from app.routers import admin, public

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Creates missing tables on start; add Alembic once the schema needs migrations.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Photo Vault & Locker themes", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="pv_admin",
    https_only=settings.cookie_secure,
    same_site="lax",
    max_age=60 * 60 * 12,
)
app.include_router(public.router)
app.include_router(admin.router)
app.mount("/admin/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

if settings.storage_backend == "local":
    media = Path(settings.local_media_dir)
    media.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media), name="media")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/admin")
