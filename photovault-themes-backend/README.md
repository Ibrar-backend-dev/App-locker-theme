# Photo Vault & Locker — themes backend

Own backend for the app's lock-screen themes, replacing the shared `prod-fastapi-backend.aspire.pics`.

- **Public API** (read-only, used by the app): same paths, query parameters and JSON as before,
  so the app only changes its base URL.
- **Admin panel** at `/admin`: sign in, create categories, upload images / GIFs / videos,
  set premium, order and visibility.
- **Files** go to an S3-compatible bucket (AWS S3, Cloudflare R2, DigitalOcean Spaces) and are
  served by a CDN over https when configured; without S3 credentials, files use local `media/`.

Stack: FastAPI, SQLAlchemy 2, SQLite by default (PostgreSQL supported), boto3.

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
cp .env.example .env        # set a private ADMIN_PASSWORD and SECRET_KEY
docker compose up --build
```
Open http://localhost:8000/admin. Docker Compose uses SQLite and stores uploads in a persistent
local volume by default. No database or S3 credentials are needed for local development.
To use PostgreSQL, set `DATABASE_URL`; to use S3-compatible storage, set `STORAGE_BACKEND=s3`,
`S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and `CDN_BASE_URL`.

### Test with Insomnia

Import `App_Locker_Backend.insomnia.json` into Insomnia and start the API. Select the `Local`
environment to test the three public API endpoints used by the app. Set `category_id` to an
existing category ID before sending the category artworks request.

## Run the tests

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
pytest
```
Tests use SQLite and local file storage in a temp folder; no database or bucket needed.

## Deploy

1. A Postgres database (managed) configured with `DATABASE_URL`.
2. A bucket with public read through a CDN domain (e.g. R2 + a custom domain). Set `S3_*` and `CDN_BASE_URL`.
3. Run the container behind https (Caddy / Nginx / a platform load balancer). Keep `COOKIE_SECURE=true`.
4. Upload categories and themes in `/admin`.
5. In the Android project set `PHOTOVAULT_THEMES_BASE_URL=https://<your-api-domain>/` in
   `gradle.properties` (it must end with `/`) and build.

Tables are created on start-up. When the schema starts changing, add Alembic migrations.

### Deploy on Railway without PostgreSQL or S3

The Dockerfile reads Railway's `PORT`. Create a Railway service from the repository and set its
Root Directory to `/photovault-themes-backend` so it finds the Dockerfile. In the service settings,
create a volume mounted at `/data`; SQLite and uploaded files must share this one persistent volume.

Set these service variables in Railway (replace the values in angle brackets):

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<a-strong-unique-password>
SECRET_KEY=<a-long-random-secret>
COOKIE_SECURE=true
DATABASE_URL=sqlite:////data/app.db
STORAGE_BACKEND=local
LOCAL_MEDIA_DIR=/data/media
PUBLIC_BASE_URL=https://<your-railway-domain>
```

Generate a secret locally in PowerShell with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Generate a separate value for
`ADMIN_PASSWORD`. Do not commit these values or put them in the Docker image.

Set Railway's health check path to `/health`. After deployment, open
`https://<your-railway-domain>/health`; it should return `{"status":"ok"}`. This setup does not
need PostgreSQL or S3 credentials. The mounted volume keeps the SQLite database and uploads
across redeploys, but SQLite is intended for a single service replica. For production CDN-backed
media or horizontal scaling, use PostgreSQL and S3-compatible storage instead.
