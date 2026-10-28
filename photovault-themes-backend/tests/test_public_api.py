"""The public API must keep the exact contract the Android app (ThemeDtos.kt / ThemeApiService.kt) expects."""

import re

from app.models import Artwork, Category

PREFIX = "/api/locker-theme/public"
CATEGORY_KEYS = {"id", "name", "description", "position", "thumbnail_path", "artwork_count"}
ARTWORK_KEYS = {
    "id", "category_id", "title", "media_type", "is_premium",
    "original_filename", "file_path", "gif_path", "created_at",
}


def seed(db):
    nature = Category(name="Nature", position=1, thumbnail_key="themes/categories/n.jpg")
    anime = Category(name="Anime", position=0)
    empty = Category(name="Empty", position=2)
    hidden = Category(name="Hidden", position=3, is_active=False)
    db.add_all([nature, anime, empty, hidden])
    db.flush()
    db.add_all([
        Artwork(category_id=nature.id, media_type="image", file_key="themes/artworks/a.jpg", title="Lake"),
        Artwork(category_id=nature.id, media_type="video", file_key="themes/artworks/b.mp4",
                gif_key="themes/previews/b.gif", is_premium=True),
        Artwork(category_id=anime.id, media_type="image", file_key="themes/artworks/c.gif",
                gif_key="themes/artworks/c.gif"),
        Artwork(category_id=anime.id, media_type="image", file_key="themes/artworks/off.jpg", is_active=False),
        Artwork(category_id=hidden.id, media_type="image", file_key="themes/artworks/h.jpg"),
    ])
    db.commit()
    return nature, anime


def test_categories_contract_and_order(client, db):
    seed(db)
    body = client.get(f"{PREFIX}/categories", params={
        "include_empty": False, "page": 1, "page_size": 100, "type": "all"}).json()

    assert set(body) == {"data", "meta"}
    assert body["meta"] == {"page": 1, "page_size": 100, "total": 2, "has_next": False}
    assert [c["name"] for c in body["data"]] == ["Anime", "Nature"]  # by position; empty + hidden left out
    for c in body["data"]:
        assert set(c) == CATEGORY_KEYS
    nature = body["data"][1]
    assert nature["artwork_count"] == 2
    assert nature["thumbnail_path"] == "https://themes.test/media/themes/categories/n.jpg"
    assert body["data"][0]["artwork_count"] == 1  # inactive artwork not counted


def test_categories_include_empty_and_type(client, db):
    seed(db)
    names = [c["name"] for c in client.get(f"{PREFIX}/categories", params={"include_empty": True}).json()["data"]]
    assert names == ["Anime", "Nature", "Empty"]

    videos = client.get(f"{PREFIX}/categories", params={"type": "video"}).json()["data"]
    assert [(c["name"], c["artwork_count"]) for c in videos] == [("Nature", 1)]


def test_artworks_contract_filters_and_paging(client, db):
    seed(db)
    body = client.get(f"{PREFIX}/artworks", params={
        "page": 1, "page_size": 2, "type": "all", "premium_only": False}).json()
    assert body["meta"] == {"page": 1, "page_size": 2, "total": 3, "has_next": True}
    for a in body["data"]:
        assert set(a) == ARTWORK_KEYS
        assert a["file_path"].startswith("https://")  # the app drops non-https links
        assert re.match(r"\d{4}-\d{2}-\d{2}T", a["created_at"])

    page2 = client.get(f"{PREFIX}/artworks", params={"page": 2, "page_size": 2}).json()
    assert page2["meta"]["has_next"] is False and len(page2["data"]) == 1

    premium = client.get(f"{PREFIX}/artworks", params={"premium_only": True}).json()["data"]
    assert len(premium) == 1 and premium[0]["media_type"] == "video"
    assert premium[0]["gif_path"].endswith("themes/previews/b.gif")

    images = client.get(f"{PREFIX}/artworks", params={"type": "image"}).json()["data"]
    assert {a["media_type"] for a in images} == {"image"} and len(images) == 2


def test_category_artworks(client, db):
    nature, anime = seed(db)
    data = client.get(f"{PREFIX}/categories/{anime.id}/artworks", params={"type": "all"}).json()["data"]
    assert len(data) == 1 and data[0]["category_id"] == anime.id
    assert data[0]["gif_path"] == data[0]["file_path"]  # GIF is its own animated preview

    assert client.get(f"{PREFIX}/categories/999999/artworks").status_code == 404


def test_page_size_limit(client):
    assert client.get(f"{PREFIX}/artworks", params={"page_size": 101}).status_code == 422
