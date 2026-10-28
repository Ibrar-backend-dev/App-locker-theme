"""Admin web panel (/admin): sign in, manage categories, upload and edit theme images and videos.

Simple server-rendered pages with plain HTML forms. One admin account from the settings;
a session cookie keeps you signed in, and every form carries a CSRF token.
"""

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Artwork, Category
from app.storage import get_storage, new_key

router = APIRouter(prefix="/admin", include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/webm"}


# ---------------------------------------------------------------------------------------
# Session, CSRF
# ---------------------------------------------------------------------------------------

def _csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


def _check_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf")
    if not expected or not secrets.compare_digest(expected, token or ""):
        raise HTTPException(status_code=400, detail="Form expired, reload the page and try again")


def require_admin(request: Request) -> None:
    if not request.session.get("admin"):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


def _render(request: Request, name: str, **context):
    return templates.TemplateResponse(
        request, name, {"csrf": _csrf(request), "url": get_storage().url, **context}
    )


def _back(path: str, message: str | None = None) -> RedirectResponse:
    return RedirectResponse(path + (f"?msg={message}" if message else ""), status_code=303)


# ---------------------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------------------

async def _read_upload(upload: UploadFile, allowed: set[str]) -> bytes:
    if upload.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload.content_type}")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=400, detail=f"File is larger than {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return data


async def _store(upload: UploadFile, allowed: set[str], kind: str) -> str:
    data = await _read_upload(upload, allowed)
    key = new_key(kind, upload.filename)
    get_storage().save(key, data, upload.content_type)
    return key


def _delete_files(*keys: str | None) -> None:
    storage = get_storage()
    for key in {k for k in keys if k}:
        try:
            storage.delete(key)
        except Exception:  # a missing file must not block the database change
            pass


def _has_file(upload: UploadFile | None) -> bool:
    return upload is not None and bool(upload.filename)


# ---------------------------------------------------------------------------------------
# Sign in / out
# ---------------------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return _render(request, "login.html", error=None)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), csrf: str = Form("")):
    _check_csrf(request, csrf)
    s = get_settings()
    # Bytes, so non-ASCII input can't raise; both checks always run (no timing hint).
    ok = secrets.compare_digest(username.encode(), s.admin_username.encode()) & secrets.compare_digest(
        password.encode(), s.admin_password.encode()
    )
    if not ok:
        return _render(request, "login.html", error="Wrong username or password")
    request.session.clear()
    request.session["admin"] = True
    return _back("/admin")


@router.post("/logout")
def logout(request: Request, csrf: str = Form("")):
    _check_csrf(request, csrf)
    request.session.clear()
    return _back("/admin/login")


# ---------------------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def categories_page(request: Request, msg: str | None = None, db: Session = Depends(get_db)):
    counts = dict(
        db.execute(select(Artwork.category_id, func.count(Artwork.id)).group_by(Artwork.category_id)).all()
    )
    categories = db.scalars(select(Category).order_by(Category.position, func.lower(Category.name))).all()
    return _render(request, "categories.html", categories=categories, counts=counts, msg=msg)


@router.post("/categories", dependencies=[Depends(require_admin)])
async def create_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    position: int = Form(0),
    thumbnail: UploadFile | None = File(None),
    csrf: str = Form(""),
    db: Session = Depends(get_db),
):
    _check_csrf(request, csrf)
    if not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    category = Category(name=name.strip(), description=description.strip() or None, position=position)
    if _has_file(thumbnail):
        category.thumbnail_key = await _store(thumbnail, IMAGE_TYPES, "categories")
    db.add(category)
    db.commit()
    return _back(f"/admin/categories/{category.id}", "Category created")


@router.get("/categories/{category_id}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def category_page(request: Request, category_id: int, msg: str | None = None, db: Session = Depends(get_db)):
    category = db.get(Category, category_id) or _not_found()
    artworks = db.scalars(
        select(Artwork)
        .where(Artwork.category_id == category_id)
        .order_by(Artwork.position, Artwork.created_at.desc(), Artwork.id.desc())
    ).all()
    others = db.scalars(select(Category).order_by(Category.position, func.lower(Category.name))).all()
    return _render(request, "category.html", category=category, artworks=artworks, categories=others, msg=msg)


@router.post("/categories/{category_id}/update", dependencies=[Depends(require_admin)])
async def update_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    description: str = Form(""),
    position: int = Form(0),
    is_active: bool = Form(False),
    thumbnail: UploadFile | None = File(None),
    csrf: str = Form(""),
    db: Session = Depends(get_db),
):
    _check_csrf(request, csrf)
    category = db.get(Category, category_id) or _not_found()
    category.name = name.strip() or category.name
    category.description = description.strip() or None
    category.position = position
    category.is_active = is_active
    old_thumbnail = None
    if _has_file(thumbnail):
        old_thumbnail, category.thumbnail_key = category.thumbnail_key, await _store(thumbnail, IMAGE_TYPES, "categories")
    db.commit()
    _delete_files(old_thumbnail)
    return _back(f"/admin/categories/{category_id}", "Saved")


@router.post("/categories/{category_id}/delete", dependencies=[Depends(require_admin)])
def delete_category(request: Request, category_id: int, csrf: str = Form(""), db: Session = Depends(get_db)):
    _check_csrf(request, csrf)
    category = db.get(Category, category_id) or _not_found()
    keys = [category.thumbnail_key] + [k for a in category.artworks for k in (a.file_key, a.gif_key)]
    db.delete(category)
    db.commit()
    _delete_files(*keys)
    return _back("/admin", "Category deleted")


# ---------------------------------------------------------------------------------------
# Artworks
# ---------------------------------------------------------------------------------------

@router.post("/categories/{category_id}/artworks", dependencies=[Depends(require_admin)])
async def upload_artwork(
    request: Request,
    category_id: int,
    file: UploadFile = File(...),
    preview_gif: UploadFile | None = File(None),
    title: str = Form(""),
    position: int = Form(0),
    is_premium: bool = Form(False),
    csrf: str = Form(""),
    db: Session = Depends(get_db),
):
    _check_csrf(request, csrf)
    db.get(Category, category_id) or _not_found()

    media_type = "video" if file.content_type in VIDEO_TYPES else "image"
    file_key = await _store(file, IMAGE_TYPES | VIDEO_TYPES, "artworks")
    # Animated preview: a GIF image is its own preview; a video may get a separate GIF.
    gif_key = file_key if file.content_type == "image/gif" else None
    if _has_file(preview_gif):
        gif_key = await _store(preview_gif, {"image/gif"}, "previews")

    db.add(
        Artwork(
            category_id=category_id,
            title=title.strip() or None,
            media_type=media_type,
            is_premium=is_premium,
            original_filename=Path(file.filename or "").name or None,
            file_key=file_key,
            gif_key=gif_key,
            position=position,
        )
    )
    db.commit()
    return _back(f"/admin/categories/{category_id}", "Uploaded")


@router.post("/artworks/{artwork_id}/update", dependencies=[Depends(require_admin)])
def update_artwork(
    request: Request,
    artwork_id: int,
    title: str = Form(""),
    position: int = Form(0),
    category_id: int = Form(...),
    is_premium: bool = Form(False),
    is_active: bool = Form(False),
    csrf: str = Form(""),
    db: Session = Depends(get_db),
):
    _check_csrf(request, csrf)
    artwork = db.get(Artwork, artwork_id) or _not_found()
    db.get(Category, category_id) or _not_found()
    back_to = artwork.category_id
    artwork.title = title.strip() or None
    artwork.position = position
    artwork.category_id = category_id
    artwork.is_premium = is_premium
    artwork.is_active = is_active
    db.commit()
    return _back(f"/admin/categories/{back_to}", "Saved")


@router.post("/artworks/{artwork_id}/delete", dependencies=[Depends(require_admin)])
def delete_artwork(request: Request, artwork_id: int, csrf: str = Form(""), db: Session = Depends(get_db)):
    _check_csrf(request, csrf)
    artwork = db.get(Artwork, artwork_id) or _not_found()
    category_id, keys = artwork.category_id, (artwork.file_key, artwork.gif_key)
    db.delete(artwork)
    db.commit()
    _delete_files(*keys)
    return _back(f"/admin/categories/{category_id}", "Deleted")


def _not_found():
    raise HTTPException(status_code=404, detail="Not found")
