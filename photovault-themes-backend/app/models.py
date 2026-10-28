"""Tables: theme categories and the artworks (images / videos) inside them.

Files are stored by key (path in the bucket); public https URLs are built from the key when
a response is made, so moving to another CDN only needs a settings change.
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# BIGINT ids in Postgres; SQLite only auto-increments INTEGER primary keys.
Id = BigInteger().with_variant(Integer, "sqlite")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Id, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    thumbnail_key: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    artworks: Mapped[list["Artwork"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )


class Artwork(Base):
    __tablename__ = "artworks"
    __table_args__ = (Index("ix_artworks_category_active", "category_id", "is_active"),)

    id: Mapped[int] = mapped_column(Id, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(160), default=None)
    media_type: Mapped[str] = mapped_column(String(10))  # "image" | "video"
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), default=None)
    file_key: Mapped[str] = mapped_column(String(255))
    # Animated preview (GIF). For a GIF image it is the file itself.
    gif_key: Mapped[str | None] = mapped_column(String(255), default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category] = relationship(back_populates="artworks")
