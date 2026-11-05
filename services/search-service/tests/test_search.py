import os
import time
import uuid

import jwt
import pytest
from app import create_app
from app.indexer import reindex
from app.worker import sources_for
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": "x@ncit.edu.np", "name": "X", "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


DATA = {
    ("academics", "/public/departments"): {"items": [{"slug": "computer"}]},
    ("academics", "/public/departments/computer"): {"department": {
        "name": "Computer Engineering", "tagline": "Build software and hardware", "overview": "Networks, compilers and embedded systems.",
        "hod": {"name": "Er. Amit Kumar Shrivastava"}, "programmes": [{"name": "BE Computer Engineering"}], "labs": [],
        "updated_at": "2026-11-01T10:00:00+00:00"}},
    ("academics", "/public/faculty"): {"items": [{"id": "f1", "name": "Sita Sharma", "designation": "Lecturer",
                                                 "specialization": "Machine learning", "department": {"slug": "computer", "name": "Computer Engineering"}}]},
    ("content", "/public/news?page=1"): {"items": [{"slug": "robotics-sensor", "title": "Robotics club builds an irrigation sensor",
                                                    "summary": "Soil moisture texts", "body": "Kavre farmers", "category": "Student life",
                                                    "publish_at": "2026-10-20T00:00:00+00:00"}], "total": 1, "per_page": 12},
    ("content", "/public/notices?page=1"): {"items": [{"id": "n1", "title": "Internal examination routine", "category": "exam",
                                                       "body": "All BE programmes", "publish_at": "2026-10-24T00:00:00+00:00"}], "total": 1, "per_page": 12},
    ("content", "/public/leadership"): {"items": [{"position": "principal", "person_name": "Er. Niranjan Khakurel",
                                                   "role_title": "Principal", "excerpt": "Discipline", "message": "Welcome"}]},
    ("events", "/public/events?limit=50"): {"items": [{"slug": "tech-fest", "title": "NCIT Tech Fest 2026", "summary": "Hackathon",
                                                       "venue": "Main campus", "start_at": "2026-12-12T03:15:00+00:00"}]},
    ("events", "/public/events?limit=50&when=past"): {"items": []},
    ("eca", "/public/clubs"): {"items": [{"slug": "robotics-club"}]},
    ("eca", "/public/clubs/robotics-club"): {"club": {"name": "Robotics Club", "tagline": "Robots and drones", "about": "Compete nationally"},
                                             "activities": [{"title": "Sensor field test"}]},
    ("careers", "/public/jobs"): {"items": [{"slug": "lecturer-computer"}]},
    ("careers", "/public/jobs/lecturer-computer"): {"job": {"title": "Lecturer, Computer Engineering", "summary": "Teach programming",
                                                            "department": "Computer", "description": "", "requirements": "ME"}},
    ("admissions", "/public/intakes"): {"items": [{"name": "Fall 2026", "offerings": [
        {"id": "o1", "programme": "BE Civil Engineering", "seats": 48, "eligibility": "+2 Science", "fee_note": ""}]}]},
}


class Fetcher:
    def __init__(self):
        self.down = set()

    def __call__(self, source, path):
        if source in self.down:
            raise ConnectionError("service down")
        return DATA[(source, path)]


@pytest.fixture
def fetch():
    return Fetcher()


@pytest.fixture
def app(tmp_path, fetch):
    # TEST_DATABASE_URL=postgresql+psycopg://… runs the same tests on PostgreSQL's full-text search
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/s.db"
    app = create_app({"DATABASE_URL": url, "JWT_PUBLIC_KEY": PUBLIC, "FETCH": fetch, "SITE_URL": "https://ncit.edu.np"})
    if not url.startswith("sqlite"):
        from app.models import Base

        engine = app.extensions["db"]().get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    with app.app_context():
        assert all(isinstance(v, int) for v in reindex(app.extensions["db"](), fetch).values())
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def titles(client, q, kind=""):
    return [i["title"] for i in client.get(f"/public/search?q={q}&kind={kind}").json["items"]]


def test_finds_everything_across_services(client):
    assert titles(client, "computer")[0] == "Computer Engineering"  # title match ranks first
    assert "Sita Sharma" in titles(client, "machine learning")
    assert titles(client, "tech fest") == ["NCIT Tech Fest 2026"]
    assert titles(client, "exam")[0] == "Internal examination routine"
    assert "Robotics Club" in titles(client, "robot")  # word prefix
    assert titles(client, "civil") == ["BE Civil Engineering"]
    assert titles(client, "contact") == ["Contact and directions"]
    res = client.get("/public/search?q=robot").json
    assert res["kinds"] == {"news": 1, "club": 1} and res["labels"]["club"] == "Clubs"
    assert titles(client, "robot", "club") == ["Robotics Club"]


def test_every_word_must_match_and_odd_input_is_safe(client):
    assert titles(client, "computer fest") == []
    for q in ("", "%", "' OR 1=1 --", "<script>", "a" * 500):
        assert client.get(f"/public/search?q={q}").status_code == 200
    assert client.get("/public/search?q=computer&page=abc").status_code == 200


def test_unreachable_service_keeps_its_old_results(app, client, fetch):
    fetch.down.add("events")
    with app.app_context():
        result = reindex(app.extensions["db"](), fetch)
    assert result["events"].startswith("failed") and result["content"] >= 1
    assert titles(client, "tech fest") == ["NCIT Tech Fest 2026"]


def test_sitemap_has_canonical_pages_only(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "<loc>https://ncit.edu.np/departments/computer</loc><lastmod>2026-11-01</lastmod>" in xml
    assert "https://ncit.edu.np/news/robotics-sensor" in xml and "https://ncit.edu.np/clubs/robotics-club" in xml
    assert "#" not in xml and "?q=" not in xml  # no notice anchors or faculty search links
    assert "<loc>https://ncit.edu.np/</loc>" in xml


def test_rebuild_and_status_are_for_super_admins(client):
    assert client.post("/reindex", headers=auth("content_admin")).status_code == 403
    res = client.post("/reindex", json={"sources": ["careers"]}, headers=auth("super_admin"))
    assert res.json["result"] == {"careers": 1}
    status = client.get("/status", headers=auth("super_admin")).json["sources"]
    assert status["academics"]["documents"] == 2


def test_events_map_to_sources():
    assert sources_for([{"service": "content-service"}, {"service": "auth-service"}, {"service": "eca-service"}]) == {"content", "eca"}
