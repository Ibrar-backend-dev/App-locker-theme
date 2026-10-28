"""Response shapes. Field names match the Android app's ThemeDtos.kt exactly."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageMetaDto(BaseModel):
    page: int
    page_size: int
    total: int
    has_next: bool


class PagedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMetaDto


class ThemeCategoryDto(BaseModel):
    id: int
    name: str
    description: str | None
    position: int
    thumbnail_path: str | None
    artwork_count: int


class ThemeArtworkDto(BaseModel):
    id: int
    category_id: int
    title: str | None
    media_type: str
    is_premium: bool
    original_filename: str | None
    file_path: str
    gif_path: str | None
    created_at: str | None
