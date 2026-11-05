import io
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app import create_app
from app.seed import seed
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ncit_common import MemoryEventPublisher
from PIL import Image

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles, email="user@ncit.edu.np"):
    now = time.time()
    claims = {"sub": email, "email": email, "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


SUPER = auth("super_admin", email="admin@ncit.edu.np")
EDITOR = auth("content_admin", email="editor@ncit.edu.np")
HOD = auth("hod")


def iso(delta_hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=delta_hours)).isoformat()


@pytest.fixture
def events():
    return MemoryEventPublisher("content-service")


@pytest.fixture
def app(tmp_path, events):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/c.db", "JWT_PUBLIC_KEY": PUBLIC,
                      "MEDIA_ROOT": str(tmp_path / "media"), "EVENTS": events})
    with app.app_context():
        seed(app.extensions["db"]())
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def home(client):
    return client.get("/public/home").json


def test_seed_matches_current_home_page(client, app):
    data = home(client)
    assert data["banners"][0]["title"] == "Build what Nepal needs next."
    assert [m["person_name"] for m in data["leadership"]] == [
        "Mr. Bijuli Prasad Rana", "Dr. Krishna Chandra Poudel", "Er. Niranjan Khakurel"]
    assert len(data["news"]) == 4 and len(data["notices"]) == 4 and len(data["facilities"]) == 6
    with app.app_context():
        assert seed(app.extensions["db"]()) == []  # idempotent


def test_gate_schedule_a_banner(client, events):
    """Phase 2 gate, part 1: a scheduled banner appears only inside its window."""
    future = client.post("/banners", json={"title": "Open day", "published": True,
                                           "start_at": iso(2), "end_at": iso(48)}, headers=SUPER).json["item"]
    assert future["status"] == "scheduled"
    assert "Open day" not in [b["title"] for b in home(client)["banners"]]

    client.patch(f"/banners/{future['id']}", json={"start_at": iso(-1)}, headers=SUPER)
    assert "Open day" in [b["title"] for b in home(client)["banners"]]

    client.patch(f"/banners/{future['id']}", json={"end_at": iso(-0.5)}, headers=SUPER)
    listed = {b["id"]: b for b in client.get("/banners", headers=SUPER).json["items"]}
    assert listed[future["id"]]["status"] == "expired"
    assert "Open day" not in [b["title"] for b in home(client)["banners"]]
    assert events.events[0]["type"] == "banners.created"


def test_gate_publish_a_leadership_message(client):
    """Phase 2 gate, part 2: publishing a message puts it on the website."""
    items = client.get("/leadership", headers=SUPER).json["items"]
    principal = next(i for i in items if i["position"] == "principal")
    client.patch(f"/leadership/{principal['id']}", json={"published": False}, headers=SUPER)
    assert "Er. Niranjan Khakurel" not in [m["person_name"] for m in client.get("/public/leadership").json["items"]]
    res = client.patch(f"/leadership/{principal['id']}", json={"message": "Welcome to NCIT.\n\nStudy hard.",
                                                               "published": True}, headers=SUPER)
    assert res.json["item"]["status"] == "live"
    page = {m["position"]: m for m in client.get("/public/leadership").json["items"]}
    assert page["principal"]["message"].startswith("Welcome to NCIT.")


def test_banner_window_must_make_sense(client):
    res = client.post("/banners", json={"title": "X", "start_at": iso(5), "end_at": iso(1)}, headers=SUPER)
    assert res.status_code == 422 and res.json["error"]["code"] == "invalid_window"


def test_content_admin_can_edit_but_hod_cannot(client):
    assert client.post("/notices", json={"title": "Fee deadline", "published": True}, headers=EDITOR).status_code == 201
    assert client.post("/notices", json={"title": "x"}, headers=HOD).status_code == 403
    assert client.get("/banners").status_code == 401


def test_news_slug_schedule_and_detail(client):
    a = client.post("/news", json={"title": "NCIT wins hackathon!", "body": "Details.", "published": True},
                    headers=EDITOR).json["item"]
    assert a["slug"] == "ncit-wins-hackathon" and a["status"] == "live" and a["publish_at"]
    b = client.post("/news", json={"title": "NCIT wins hackathon!", "published": True, "publish_at": iso(24)},
                    headers=EDITOR).json["item"]
    assert b["slug"] == "ncit-wins-hackathon-2" and b["status"] == "scheduled"
    assert client.get("/public/news/ncit-wins-hackathon").status_code == 200
    assert client.get("/public/news/ncit-wins-hackathon-2").status_code == 404
    assert client.get("/public/news").json["items"][0]["slug"] == "ncit-wins-hackathon"


def test_notices_pinned_first_and_expiry(client):
    pin = client.post("/notices", json={"title": "Pinned notice", "pinned": True, "published": True,
                                        "publish_at": iso(-100)}, headers=EDITOR).json["item"]
    client.post("/notices", json={"title": "Expired notice", "published": True, "publish_at": iso(-10),
                                  "expires_at": iso(-1)}, headers=EDITOR)
    titles = [n["title"] for n in client.get("/public/notices").json["items"]]
    assert titles[0] == "Pinned notice" and "Expired notice" not in titles
    exam = client.get("/public/notices?category=exam").json["items"]
    assert all(n["category"] == "exam" for n in exam)
    assert pin["status"] == "live"


def test_drafts_never_public(client):
    client.post("/news", json={"title": "Secret draft"}, headers=EDITOR)
    assert "Secret draft" not in [n["title"] for n in client.get("/public/news").json["items"]]
    assert "published" not in home(client)["news"][0]


def test_only_one_message_per_position(client):
    res = client.post("/leadership", json={"position": "director", "person_name": "Someone"}, headers=SUPER)
    assert res.status_code == 409


def test_reorder_and_delete(client):
    items = client.get("/facilities", headers=EDITOR).json["items"]
    ids = [i["id"] for i in items][::-1]
    assert client.post("/facilities/order", json={"ids": ids}, headers=EDITOR).status_code == 200
    assert home(client)["facilities"][0]["name"] == "Transport"
    assert client.delete(f"/facilities/{ids[0]}", headers=EDITOR).status_code == 200
    assert len(home(client)["facilities"]) == 5
    assert client.post("/news/order", json={"ids": []}, headers=EDITOR).status_code == 422


def test_uploads(client):
    buf = io.BytesIO()
    Image.new("RGB", (2000, 800), "navy").save(buf, "JPEG")
    res = client.post("/uploads", data={"file": (io.BytesIO(buf.getvalue()), "b.jpg"), "kind": "image", "group": "banners"},
                      headers=EDITOR, content_type="multipart/form-data")
    assert res.status_code == 201 and res.json["url"].startswith("/media/content/banners/")
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    res = client.post("/uploads", data={"file": (pdf, "routine.pdf"), "kind": "pdf", "group": "notices"},
                      headers=EDITOR, content_type="multipart/form-data")
    assert res.status_code == 201 and res.json["url"].endswith(".pdf")
    url = res.json["url"]
    assert client.post("/notices", json={"title": "Routine", "attachment": url}, headers=EDITOR).status_code == 201
    fake = client.post("/uploads", data={"file": (io.BytesIO(b"not a pdf"), "x.pdf"), "kind": "pdf"},
                       headers=EDITOR, content_type="multipart/form-data")
    assert fake.json["error"]["code"] == "not_a_pdf"


def test_datetime_without_zone_is_nepal_time(client):
    item = client.post("/banners", json={"title": "Local time", "start_at": "2030-01-01T09:00"}, headers=SUPER).json["item"]
    assert item["start_at"].startswith("2030-01-01T03:15:00")


def test_contact_form_goes_to_the_college_only(app, client):
    from ncit_common.mail import MemoryMailQueue

    mail = MemoryMailQueue("content-service")
    app.config["MAIL"] = mail
    ok = client.post("/public/contact", json={"name": "Ada", "email": "ada@gmail.com", "topic": "fees",
                                              "message": "When is the second instalment due?"})
    assert ok.status_code == 200
    assert [m["to"] for m in mail.messages] == ["info@ncit.edu.np"]
    assert mail.messages[0]["data"]["topic"] == "Fees and payments" and mail.messages[0]["data"]["email"] == "ada@gmail.com"
    assert client.post("/public/contact", json={"name": "Ada", "email": "nope", "message": "x" * 20}).status_code == 422
    assert client.post("/public/contact", json={"name": "Ada", "email": "a@b.co", "message": "hi"}).status_code == 422
    bot = client.post("/public/contact", json={"name": "Bot", "email": "b@b.co", "message": "buy now " * 5, "website": "x"})
    assert bot.status_code == 200 and len(mail.messages) == 1


def test_cached_public_pages_show_edits_at_once(tmp_path, events):
    """The Redis page cache (here in memory): repeat reads skip the database, an edit shows immediately."""
    from ncit_common.cache import MemoryPublicCache

    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/cache.db", "JWT_PUBLIC_KEY": PUBLIC,
                      "MEDIA_ROOT": str(tmp_path / "media"), "EVENTS": events, "PUBLIC_CACHE": MemoryPublicCache("content")})
    with app.app_context():
        seed(app.extensions["db"]())
    c = app.test_client()
    assert c.get("/public/news").headers["X-App-Cache"] == "MISS"
    before = c.get("/public/news")
    assert before.headers["X-App-Cache"] == "HIT"
    assert c.post("/news", json={"title": "Cache test article", "published": True}, headers=EDITOR).status_code == 201
    after = c.get("/public/news")
    assert after.headers["X-App-Cache"] == "MISS"
    assert after.json["items"][0]["title"] == "Cache test article"
    assert "X-App-Cache" not in c.get("/news", headers=EDITOR).headers  # editor lists are never cached
