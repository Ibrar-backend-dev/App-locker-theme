"""Admin panel: sign-in is required, and an uploaded theme shows up in the public API."""

import re

PREFIX = "/api/locker-theme/public"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def csrf_of(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def sign_in(client) -> str:
    token = csrf_of(client.get("/admin/login").text)
    r = client.post("/admin/login", data={"username": "admin", "password": "secret", "csrf": token},
                    follow_redirects=False)
    assert r.status_code == 303
    return csrf_of(client.get("/admin").text)


def test_admin_requires_sign_in(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"


def test_wrong_password(client):
    token = csrf_of(client.get("/admin/login").text)
    r = client.post("/admin/login", data={"username": "admin", "password": "nope", "csrf": token})
    assert "Wrong username or password" in r.text


def test_post_without_csrf_is_rejected(client):
    sign_in(client)
    r = client.post("/admin/categories", data={"name": "X", "csrf": "bad"}, follow_redirects=False)
    assert r.status_code == 400


def test_create_category_upload_and_publish(client):
    token = sign_in(client)
    r = client.post("/admin/categories", data={"name": "Neon", "position": "0", "csrf": token},
                    follow_redirects=False)
    assert r.status_code == 303
    category_id = int(re.search(r"/admin/categories/(\d+)", r.headers["location"]).group(1))

    r = client.post(
        f"/admin/categories/{category_id}/artworks",
        data={"title": "Glow", "position": "0", "is_premium": "true", "csrf": token},
        files={"file": ("glow.png", PNG, "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303

    data = client.get(f"{PREFIX}/categories/{category_id}/artworks").json()["data"]
    assert len(data) == 1
    art = data[0]
    assert art["title"] == "Glow" and art["is_premium"] is True and art["media_type"] == "image"
    assert art["original_filename"] == "glow.png" and art["gif_path"] is None
    assert art["file_path"].startswith("https://themes.test/media/themes/artworks/")

    # The stored file is served back.
    assert client.get(art["file_path"].replace("https://themes.test", "")).content == PNG

    # Unsupported files are refused.
    r = client.post(f"/admin/categories/{category_id}/artworks", data={"csrf": token},
                    files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400
