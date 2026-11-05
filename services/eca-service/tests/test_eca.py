import time
import uuid

import jwt
import pytest
from app import create_app
from app.seed import seed
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ncit_common import MemoryEventPublisher

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles, email="student@ncit.edu.np", name="A Student"):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": email, "name": name, "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


SUPER = auth("super_admin", email="admin@ncit.edu.np")
ECA = auth("eca_admin", email="eca@ncit.edu.np")
EVENTS = auth("event_admin", email="events@ncit.edu.np")
STUDENT = auth(email="ram@ncit.edu.np", name="Ram Shrestha")


@pytest.fixture
def events():
    return MemoryEventPublisher("eca-service")


@pytest.fixture
def client(tmp_path, events):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/e.db", "JWT_PUBLIC_KEY": PUBLIC,
                      "MEDIA_ROOT": str(tmp_path / "media"), "EVENTS": events})
    with app.app_context():
        seed(app.extensions["db"]())
    return app.test_client()


def club_id(client, slug):
    return next(c["id"] for c in client.get("/clubs", headers=ECA).json["items"] if c["slug"] == slug)


def test_seed_and_public(client):
    clubs = client.get("/public/clubs").json["items"]
    assert [c["name"] for c in clubs][:2] == ["Robotics Club", "Coding Club"]
    assert all("pending_count" not in c and "about" not in c for c in clubs)
    page = client.get("/public/clubs/robotics-club").json
    assert page["club"]["about"] and page["activities"][0]["club"]["slug"] == "robotics-club"
    assert len(client.get("/public/activities?limit=2").json["items"]) == 2
    assert client.get("/public/clubs?category=sports").json["items"][0]["slug"] == "sports-club"


def test_gate_eca_admin_and_event_admin_are_separate(client):
    """Phase 4 gate (ECA side): an Event Admin can't create or edit clubs or decide memberships."""
    cid = club_id(client, "coding-club")
    assert client.post("/clubs", json={"name": "Chess"}, headers=EVENTS).status_code == 403
    assert client.patch(f"/clubs/{cid}", json={"name": "Hijack"}, headers=EVENTS).status_code == 403
    assert client.post("/activities", json={"club_id": cid, "title": "x"}, headers=EVENTS).status_code == 403
    assert client.get(f"/clubs/{cid}/members", headers=EVENTS).status_code == 403
    assert client.get("/requests/pending", headers=EVENTS).status_code == 403
    assert client.get("/clubs", headers=STUDENT).status_code == 403
    assert client.post("/clubs", json={"name": "Chess Club", "published": True}, headers=ECA).status_code == 201
    assert client.get("/clubs", headers=SUPER).status_code == 200


def test_join_approve_position_leave(client, events):
    res = client.post("/me/clubs/robotics-club/join", json={"message": "I build drones."}, headers=STUDENT)
    assert res.status_code == 201 and res.json["membership"]["status"] == "pending"
    again = client.post("/me/clubs/robotics-club/join", headers=STUDENT)
    assert again.json["error"]["code"] == "already_requested"

    pending = client.get("/requests/pending", headers=ECA).json["items"]
    assert pending[0]["email"] == "ram@ncit.edu.np" and pending[0]["club"]["slug"] == "robotics-club"
    cid = pending[0]["club"]["id"]
    assert client.get("/clubs", headers=ECA).json["items"][0]["pending_count"] == 1

    mid = pending[0]["id"]
    bad = client.patch(f"/clubs/{cid}/members/{mid}", json={"position": "President"}, headers=ECA)
    assert bad.status_code == 422
    client.patch(f"/clubs/{cid}/members/{mid}", json={"status": "approved"}, headers=ECA)
    client.patch(f"/clubs/{cid}/members/{mid}", json={"position": "President"}, headers=ECA)
    page = client.get("/public/clubs/robotics-club").json
    assert page["committee"] == [{"name": "Ram Shrestha", "position": "President"}]
    assert page["club"]["member_count"] == 1
    assert [e["type"] for e in events.events] == ["memberships.requested", "memberships.approved", "memberships.updated"]

    mine = client.get("/me/memberships", headers=STUDENT).json["items"]
    assert mine[0]["status"] == "approved" and mine[0]["position"] == "President"
    assert client.delete("/me/clubs/robotics-club/join", headers=STUDENT).status_code == 200
    assert client.get("/public/clubs/robotics-club").json["committee"] == []
    assert client.get("/me/clubs/robotics-club", headers=STUDENT).json["membership"] is None


def test_rejected_can_ask_again_and_closed_clubs(client):
    client.post("/me/clubs/coding-club/join", headers=STUDENT)
    m = client.get("/requests/pending", headers=ECA).json["items"][0]
    client.patch(f"/clubs/{m['club']['id']}/members/{m['id']}", json={"status": "rejected"}, headers=ECA)
    assert client.get("/me/memberships", headers=STUDENT).json["items"][0]["status"] == "rejected"
    assert client.post("/me/clubs/coding-club/join", headers=STUDENT).status_code == 201

    cid = club_id(client, "sports-club")
    client.patch(f"/clubs/{cid}", json={"join_open": False}, headers=ECA)
    assert client.post("/me/clubs/sports-club/join", headers=STUDENT).json["error"]["code"] == "join_closed"
    assert client.post("/me/clubs/sports-club/join").status_code == 401


def test_activities_need_a_real_club_and_drafts_stay_hidden(client):
    res = client.post("/activities", json={"club_id": "00000000-0000-0000-0000-000000000000", "title": "x"}, headers=ECA)
    assert res.status_code == 422
    cid = club_id(client, "photography-club")
    client.post("/activities", json={"club_id": cid, "title": "Draft walk"}, headers=ECA)
    assert client.get(f"/activities?club_id={cid}", headers=ECA).json["items"][0]["status"] == "draft"
    assert client.get("/public/clubs/photography-club").json["activities"] == []
    client.patch(f"/clubs/{cid}", json={"published": False}, headers=ECA)
    assert client.get("/public/clubs/photography-club").status_code == 404
    assert "photography-club" not in [c["slug"] for c in client.get("/public/clubs").json["items"]]


def test_delete_club_removes_members_and_activities(client):
    client.post("/me/clubs/robotics-club/join", headers=STUDENT)
    cid = club_id(client, "robotics-club")
    assert client.delete(f"/clubs/{cid}", headers=ECA).status_code == 200
    assert client.get("/requests/pending", headers=ECA).json["items"] == []
    assert all(a["club"]["slug"] != "robotics-club" for a in client.get("/public/activities").json["items"])


def test_only_college_accounts_can_ask_to_join(client):
    """Security review: an applicant or alumni account (any email address) can't ask to join a club."""
    outsider = auth("alumni", email="someone@gmail.com")
    res = client.post("/me/clubs/robotics-club/join", json={"message": "hi"}, headers=outsider)
    assert res.status_code == 403 and res.json["error"]["code"] == "college_account_only"
    assert client.post("/me/clubs/robotics-club/join", headers=STUDENT).status_code == 201


def test_join_requests_and_decisions_are_notified(client):
    sent = client.application.config["NOTIFY"].sent
    client.post("/me/clubs/robotics-club/join", json={"message": "I build drones."}, headers=STUDENT)
    assert sent[-1]["role"] == "eca_admin" and "Robotics" in sent[-1]["title"] and sent[-1]["link"] == "/dashboard/#requests"
    m = client.get("/requests/pending", headers=ECA).json["items"][0]
    client.patch(f"/clubs/{m['club']['id']}/members/{m['id']}", json={"status": "approved"}, headers=ECA)
    assert sent[-1]["to"] == "ram@ncit.edu.np" and sent[-1]["kind"] == "success" and sent[-1]["title"].startswith("Welcome to")
    client.patch(f"/clubs/{m['club']['id']}/members/{m['id']}", json={"position": "Secretary"}, headers=ECA)
    assert sent[-1]["title"].startswith("You're now Secretary")
