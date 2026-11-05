import io
import time
import uuid

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
    claims = {"sub": email, "email": email, "roles": [{"role": r, "scope": s} for r, s in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


SUPER = auth(("super_admin", "*"), email="admin@ncit.edu.np")
HOD_COMPUTER = auth(("hod", "dept:computer"), email="hod.computer@ncit.edu.np")
STUDENT = auth(("student", "*"))


@pytest.fixture
def events():
    return MemoryEventPublisher("academics-service")


@pytest.fixture
def app(tmp_path, events):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/a.db", "JWT_PUBLIC_KEY": PUBLIC,
                      "MEDIA_ROOT": str(tmp_path / "media"), "EVENTS": events})
    with app.app_context():
        seed(app.extensions["db"]())
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_seed_is_idempotent(app):
    with app.app_context():
        assert seed(app.extensions["db"]()) == []


def test_public_list_and_page(client):
    items = client.get("/public/departments").json["items"]
    assert [d["slug"] for d in items][:2] == ["computer", "it"]
    page = client.get("/public/departments/computer").json["department"]
    assert page["hod"]["name"] == "Er. Amit Kumar Shrivastava"
    assert page["programmes"][0]["semester_count"] == 8
    assert "published" not in page


def test_unpublished_department_is_hidden(client):
    client.patch("/departments/civil", json={"published": False}, headers=SUPER)
    assert client.get("/public/departments/civil").status_code == 404
    assert "civil" not in [d["slug"] for d in client.get("/public/departments").json["items"]]


def test_hod_edits_own_department_only(client, events):
    res = client.patch("/departments/computer", json={"tagline": "Hardware meets software."}, headers=HOD_COMPUTER)
    assert res.status_code == 200
    assert res.json["department"]["updated_by"] == "hod.computer@ncit.edu.np"
    assert events.events[-1]["type"] == "department.updated"
    assert client.patch("/departments/civil", json={"tagline": "x"}, headers=HOD_COMPUTER).status_code == 403
    assert client.post("/departments/civil/faculty", json={"name": "X"}, headers=HOD_COMPUTER).status_code == 403


def test_hod_list_shows_only_their_department(client):
    assert [d["slug"] for d in client.get("/departments", headers=HOD_COMPUTER).json["items"]] == ["computer"]
    assert len(client.get("/departments", headers=SUPER).json["items"]) == 8
    assert client.get("/departments", headers=STUDENT).json["items"] == []


def test_only_super_admin_renames(client):
    res = client.patch("/departments/computer", json={"name": "Computing"}, headers=HOD_COMPUTER)
    assert res.status_code == 403 and res.json["error"]["code"] == "forbidden_field"
    assert client.patch("/departments/computer", json={"name": "Computing"}, headers=SUPER).status_code == 200


def test_validation_messages(client):
    res = client.patch("/departments/computer", json={"contact_email": "not-an-email"}, headers=HOD_COMPUTER)
    assert res.status_code == 422 and "email" in res.json["error"]["message"]
    res = client.patch("/departments/computer", json={"hod_photo": "https://evil.example/x.jpg"}, headers=HOD_COMPUTER)
    assert res.status_code == 422
    res = client.patch("/departments/computer", json={"secret": 1}, headers=HOD_COMPUTER)
    assert res.json["error"]["code"] == "unknown_field"


def test_faculty_crud_and_order(client):
    for f in client.get("/departments/computer", headers=HOD_COMPUTER).json["department"]["faculty"]:
        client.delete(f"/departments/computer/faculty/{f['id']}", headers=HOD_COMPUTER)  # clear starter entries
    a = client.post("/departments/computer/faculty", json={"name": "A", "designation": "Lecturer"}, headers=HOD_COMPUTER).json["item"]
    b = client.post("/departments/computer/faculty", json={"name": "B"}, headers=HOD_COMPUTER).json["item"]
    client.post("/departments/computer/faculty/order", json={"ids": [b["id"], a["id"]]}, headers=HOD_COMPUTER)
    page = client.get("/public/departments/computer").json["department"]
    assert [f["name"] for f in page["faculty"]] == ["B", "A"]
    client.patch(f"/departments/computer/faculty/{a['id']}", json={"designation": "Professor"}, headers=HOD_COMPUTER)
    assert client.delete(f"/departments/computer/faculty/{b['id']}", headers=HOD_COMPUTER).status_code == 200
    page = client.get("/public/departments/computer").json["department"]
    assert [(f["name"], f["designation"]) for f in page["faculty"]] == [("A", "Professor")]


def test_cannot_touch_another_departments_item_via_own_slug(client):
    item = client.post("/departments/civil/labs", json={"name": "Survey lab"}, headers=SUPER).json["item"]
    res = client.delete(f"/departments/computer/labs/{item['id']}", headers=HOD_COMPUTER)
    assert res.status_code == 404


def test_testimonials_need_approval(client):
    shown = len(client.get("/public/departments/computer").json["department"]["testimonials"])
    t = client.post("/departments/computer/testimonials", json={"student_name": "S", "quote": "Great labs."},
                    headers=HOD_COMPUTER).json["item"]
    assert len(client.get("/public/departments/computer").json["department"]["testimonials"]) == shown
    client.patch(f"/departments/computer/testimonials/{t['id']}", json={"approved": True}, headers=HOD_COMPUTER)
    assert len(client.get("/public/departments/computer").json["department"]["testimonials"]) == shown + 1


def test_semester_courses_replace(client):
    page = client.get("/departments/computer", headers=HOD_COMPUTER).json["department"]
    pid = page["programmes"][0]["id"]
    rows = [{"code": "MTH 111", "title": "Engineering Mathematics I", "credits": 3},
            {"code": "CMP 114", "title": "Problem Solving with C", "credits": 3}]
    res = client.put(f"/departments/computer/programmes/{pid}/semesters/1", json={"courses": rows}, headers=HOD_COMPUTER)
    assert res.status_code == 200 and res.json["item"]["semesters"][0]["total_credits"] == 6
    res = client.put(f"/departments/computer/programmes/{pid}/semesters/1", json={"courses": rows[:1]}, headers=HOD_COMPUTER)
    assert len(res.json["item"]["semesters"][0]["courses"]) == 1
    bad = client.put(f"/departments/computer/programmes/{pid}/semesters/9", json={"courses": rows}, headers=HOD_COMPUTER)
    assert bad.status_code == 422
    empty_title = client.put(f"/departments/computer/programmes/{pid}/semesters/2",
                             json={"courses": [{"code": "X", "title": ""}]}, headers=HOD_COMPUTER)
    assert empty_title.json["error"]["message"].startswith("Row 1:")


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGBA", (2400, 1200), (20, 40, 160, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_photo_upload_is_reencoded(client, app):
    res = client.post("/departments/computer/media", data={"file": (io.BytesIO(_png_bytes()), "hod.png")},
                      headers=HOD_COMPUTER, content_type="multipart/form-data")
    assert res.status_code == 201
    url = res.json["url"]
    assert url.startswith("/media/academics/computer/") and url.endswith(".jpg")
    from pathlib import Path
    saved = Image.open(Path(app.config["MEDIA_ROOT"]) / url.removeprefix("/media/"))
    assert saved.format == "JPEG" and max(saved.size) == 1600
    assert client.patch("/departments/computer", json={"hod_photo": url}, headers=HOD_COMPUTER).status_code == 200


def test_upload_rejects_non_images(client):
    res = client.post("/departments/computer/media", data={"file": (io.BytesIO(b"<script>alert(1)</script>"), "x.jpg")},
                      headers=HOD_COMPUTER, content_type="multipart/form-data")
    assert res.status_code == 422 and res.json["error"]["code"] == "not_an_image"


def test_super_admin_creates_department(client):
    res = client.post("/departments", json={"slug": "mechanical", "name": "Mechanical Engineering"}, headers=SUPER)
    assert res.status_code == 201 and res.json["department"]["published"] is False
    assert client.post("/departments", json={"slug": "x", "name": "Bad"}, headers=SUPER).status_code == 422
    assert client.post("/departments", json={"slug": "mechanical", "name": "Again"}, headers=SUPER).status_code == 409
    assert client.post("/departments", json={"slug": "other", "name": "No"}, headers=HOD_COMPUTER).status_code == 403


def test_editing_requires_sign_in(client):
    assert client.patch("/departments/computer", json={"tagline": "x"}).status_code == 401


def test_every_department_has_starter_content(client):
    for slug in ("computer", "it", "software", "ice", "civil", "architecture", "bca", "management"):
        d = client.get(f"/public/departments/{slug}").json["department"]
        assert d["tagline"] and d["overview"] and d["hod"]["message"], slug
        assert d["programmes"][0]["semesters"][0]["courses"], slug
        assert len(d["faculty"]) == 2 and len(d["labs"]) == 2 and len(d["testimonials"]) == 1, slug
    computer = client.get("/public/departments/computer").json["department"]
    assert computer["hod"]["name"] == "Er. Amit Kumar Shrivastava"
    assert "(sample)" in client.get("/public/departments/civil").json["department"]["hod"]["name"]


def test_starter_fill_never_overwrites_hod_work(app, client):
    from app.seed import fill_starter_content

    labs = client.get("/departments/computer", headers=HOD_COMPUTER).json["department"]["labs"]
    for lab in labs:
        client.delete(f"/departments/computer/labs/{lab['id']}", headers=HOD_COMPUTER)
    client.patch("/departments/computer", json={"tagline": "Our own words."}, headers=HOD_COMPUTER)
    with app.app_context():
        assert "computer" not in fill_starter_content(app.extensions["db"]())
    page = client.get("/public/departments/computer").json["department"]
    assert page["labs"] == [] and page["tagline"] == "Our own words."


def test_faculty_directory_lists_published_departments_only(client):
    people = client.get("/public/faculty").json["items"]
    assert people and all({"name", "designation", "department"} <= set(p) for p in people)
    assert [p["name"] for p in people] == sorted(p["name"] for p in people)
    hidden = people[0]["department"]["slug"]
    client.patch(f"/departments/{hidden}", json={"published": False}, headers=SUPER)
    assert hidden not in {p["department"]["slug"] for p in client.get("/public/faculty").json["items"]}
