# Photo Vault & Locker — themes backend

Own backend for the app's lock-screen themes, replacing the shared `prod-fastapi-backend.aspire.pics`.

- **Public API** (read-only, used by the app): same paths, query parameters and JSON as before,
  so the app only changes its base URL.
- **Admin panel** at `/admin`: sign in, create categories, upload images / GIFs / videos,
  set premium, order and visibility.
- **Files** go to an S3-compatible bucket (AWS S3, Cloudflare R2, DigitalOcean Spaces) and are
  served by a CDN over https.

Stack: FastAPI, SQLAlchemy 2, PostgreSQL, boto3.

## Public API

Base path `/api/locker-theme/public`. Every list is `{"data": [...], "meta": {"page", "page_size", "total", "has_next"}}`.

| Endpoint | Query | Returns |
|---|---|---|
| `GET /categories` | `include_empty` (bool), `page`, `page_size` (≤100), `type` (`all`/`image`/`video`) | `id, name, description, position, thumbnail_path, artwork_count` |
| `GET /artworks` | `page`, `page_size`, `type`, `premium_only` | `id, category_id, title, media_type, is_premium, original_filename, file_path, gif_path, created_at` |
| `GET /categories/{id}/artworks` | same as above | same; 404 if the category doesn't exist or is hidden |

Rules the app relies on:
- Links are full `https://` URLs (the app ignores anything else).
- `media_type` is `image` or `video`. `gif_path` is the animated preview: for a GIF image it is
  the file itself; for a video it is the optional GIF uploaded with it.
- Categories are sorted by `position`, then name; artworks by `position`, then newest.
- Hidden categories / themes and empty categories (unless `include_empty=true`) are left out.

## Run locally (Docker)

```bash
cp .env.example .env        # fill in ADMIN_*, SECRET_KEY and the S3 settings
docker compose up --build
```
Open http://localhost:8000/admin. For local testing without a bucket set `STORAGE_BACKEND=local`,
`COOKIE_SECURE=false`, `PUBLIC_BASE_URL=http://localhost:8000` (the app itself needs https links,
so use a real bucket + CDN for the app).

## Run the tests

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
pytest
```
Tests use SQLite and local file storage in a temp folder; no database or bucket needed.

## Deploy

1. A Postgres database (managed, or the `db` service from `docker-compose.yml`).
2. A bucket with public read through a CDN domain (e.g. R2 + a custom domain). Set `S3_*` and `CDN_BASE_URL`.
3. Run the container behind https (Caddy / Nginx / a platform load balancer). Keep `COOKIE_SECURE=true`.
4. Upload categories and themes in `/admin`.
5. In the Android project set `PHOTOVAULT_THEMES_BASE_URL=https://<your-api-domain>/` in
   `gradle.properties` (it must end with `/`) and build.

Tables are created on start-up. When the schema starts changing, add Alembic migrations.
