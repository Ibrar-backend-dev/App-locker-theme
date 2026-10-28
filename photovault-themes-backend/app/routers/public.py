"""Public read API used by the app. Same paths, query parameters and JSON as the old backend:

    GET {prefix}/categories?include_empty=&page=&page_size=&type=
    GET {prefix}/artworks?page=&page_size=&type=&premium_only=
    GET {prefix}/categories/{category_id}/artworks?page=&page_size=&type=&premium_only=

`type` is all | image | video (anything else counts as all). Only active items in active
categories are returned.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Artwork, Category
from app.schemas import PagedResponse, PageMetaDto, ThemeArtworkDto, ThemeCategoryDto
from app.storage import get_storage

router = APIRouter(prefix=get_settings().public_prefix, tags=["public"])

MAX_PAGE_SIZE = 100


def _media_type(value: str) -> str | None:
    value = (value or "").strip().lower()
    return value if value in ("image", "video") else None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite drops the zone; values are stored in UTC
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _page(db: Session, query: Select, page: int, page_size: int) -> tuple[list, PageMetaDto]:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    meta = PageMetaDto(page=page, page_size=page_size, total=total, has_next=page * page_size < total)
    return rows, meta


def _artwork_dto(artwork: Artwork) -> ThemeArtworkDto:
    storage = get_storage()
    return ThemeArtworkDto(
        id=artwork.id,
        category_id=artwork.category_id,
        title=artwork.title,
        media_type=artwork.media_type,
        is_premium=artwork.is_premium,
        original_filename=artwork.original_filename,
        file_path=storage.url(artwork.file_key),
        gif_path=storage.url(artwork.gif_key),
        created_at=_iso(artwork.created_at),
    )


@router.get("/categories", response_model=PagedResponse[ThemeCategoryDto])
def list_categories(
    include_empty: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    type: str = "all",
    db: Session = Depends(get_db),
):
    count = select(func.count(Artwork.id)).where(
        Artwork.category_id == Category.id, Artwork.is_active.is_(True)
    )
    if media := _media_type(type):
        count = count.where(Artwork.media_type == media)
    count = count.correlate(Category).scalar_subquery()

    query = select(Category, count.label("artwork_count")).where(Category.is_active.is_(True))
    if not include_empty:
        query = query.where(count > 0)
    query = query.order_by(Category.position, func.lower(Category.name), Category.id)

    rows, meta = _page(db, query, page, page_size)
    storage = get_storage()
    data = [
        ThemeCategoryDto(
            id=category.id,
            name=category.name,
            description=category.description,
            position=category.position,
            thumbnail_path=storage.url(category.thumbnail_key),
            artwork_count=artwork_count,
        )
        for category, artwork_count in rows
    ]
    return PagedResponse[ThemeCategoryDto](data=data, meta=meta)


def _artworks(db: Session, category_id: int | None, type: str, premium_only: bool, page: int, page_size: int):
    query = (
        select(Artwork)
        .join(Category, Category.id == Artwork.category_id)
        .where(Artwork.is_active.is_(True), Category.is_active.is_(True))
    )
    if category_id is not None:
        query = query.where(Artwork.category_id == category_id)
    if media := _media_type(type):
        query = query.where(Artwork.media_type == media)
    if premium_only:
        query = query.where(Artwork.is_premium.is_(True))
    # Manual order first, then newest.
    query = query.order_by(Artwork.position, Artwork.created_at.desc(), Artwork.id.desc())

    rows, meta = _page(db, query, page, page_size)
    return PagedResponse[ThemeArtworkDto](data=[_artwork_dto(row[0]) for row in rows], meta=meta)


@router.get("/artworks", response_model=PagedResponse[ThemeArtworkDto])
def list_artworks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    type: str = "all",
    premium_only: bool = False,
    db: Session = Depends(get_db),
):
    return _artworks(db, None, type, premium_only, page, page_size)


@router.get("/categories/{category_id}/artworks", response_model=PagedResponse[ThemeArtworkDto])
def list_category_artworks(
    category_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    type: str = "all",
    premium_only: bool = False,
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise HTTPException(status_code=404, detail="Category not found")
    return _artworks(db, category_id, type, premium_only, page, page_size)
