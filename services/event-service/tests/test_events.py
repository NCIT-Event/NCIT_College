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
EVENTS = auth("event_admin", email="events@ncit.edu.np")
ECA = auth("eca_admin", email="eca@ncit.edu.np")


def student(n):
    return auth(email=f"s{n}@ncit.edu.np", name=f"Student {n}")


def iso(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


@pytest.fixture
def events():
    return MemoryEventPublisher("event-service")


@pytest.fixture
def client(tmp_path, events):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/e.db", "JWT_PUBLIC_KEY": PUBLIC,
                      "MEDIA_ROOT": str(tmp_path / "media"), "EVENTS": events})
    with app.app_context():
        seed(app.extensions["db"]())
    return app.test_client()


def make(client, **kw):
    body = {"title": "Robotics demo", "start_at": iso(48), "published": True} | kw
    res = client.post("/events", json=body, headers=EVENTS)
    assert res.status_code == 201, res.json
    return res.json["item"]


def test_seed_and_public_lists(client):
    upcoming = client.get("/public/events").json
    assert [e["slug"] for e in upcoming["items"]][:2] == ["open-day", "workshop-cloud-deployment"]
    assert all("capacity" not in e and "published" not in e for e in upcoming["items"])
    past = client.get("/public/events?when=past").json["items"]
    assert [e["slug"] for e in past] == ["guest-lecture-payments", "futsal-quarter-finals"]
    assert client.get("/public/events/ncit-tech-fest-2026").json["event"]["registration"]["capacity"] == 120


def test_gate_event_admin_and_eca_admin_are_separate(client):
    """Phase 4 gate (event side): an ECA Admin can't create, edit or see event registrations."""
    assert client.post("/events", json={"title": "x", "start_at": iso(5)}, headers=ECA).status_code == 403
    e = make(client)
    assert client.patch(f"/events/{e['id']}", json={"title": "Hijack"}, headers=ECA).status_code == 403
    assert client.delete(f"/events/{e['id']}", headers=ECA).status_code == 403
    assert client.get(f"/events/{e['id']}/registrations", headers=ECA).status_code == 403
    assert client.get("/events", headers=student(1)).status_code == 403
    assert client.get("/events", headers=EVENTS).status_code == 200
    assert client.get("/events", headers=SUPER).status_code == 200


def test_draft_events_are_hidden(client):
    e = make(client, title="Secret planning", published=False)
    assert e["status"] == "draft"
    assert "Secret planning" not in [x["title"] for x in client.get("/public/events").json["items"]]
    assert client.get(f"/public/events/{e['slug']}").status_code == 404
    assert client.post(f"/me/events/{e['slug']}/register", headers=student(1)).status_code == 404


def test_register_waitlist_and_promotion(client, events):
    e = make(client, title="Small workshop", registration_open=True, capacity=2)
    slug = e["slug"]
    for n in (1, 2, 3):
        res = client.post(f"/me/events/{slug}/register", headers=student(n))
        assert res.status_code == 201
    third = client.get(f"/me/events/{slug}", headers=student(3)).json["registration"]
    assert third["status"] == "waitlisted" and third["waitlist_position"] == 1
    assert client.get(f"/public/events/{slug}").json["event"]["registration"]["state"] == "full"
    assert client.post(f"/me/events/{slug}/register", headers=student(1)).json["error"]["code"] == "already_registered"

    assert client.delete(f"/me/events/{slug}/register", headers=student(1)).status_code == 200
    assert client.get(f"/me/events/{slug}", headers=student(3)).json["registration"]["status"] == "registered"
    assert client.get(f"/me/events/{slug}", headers=student(1)).json["registration"] is None
    cancelled = next(x for x in events.events if x["type"] == "registrations.cancelled")
    assert cancelled["data"]["moved_up"] == ["s3@ncit.edu.np"]

    mine = client.get("/me/registrations", headers=student(3)).json["items"]
    assert mine[0]["event"]["slug"] == slug and mine[0]["status"] == "registered"


def test_more_places_move_the_waitlist_up(client):
    e = make(client, registration_open=True, capacity=1)
    for n in (1, 2):
        client.post(f"/me/events/{e['slug']}/register", headers=student(n))
    item = client.patch(f"/events/{e['id']}", json={"capacity": 2}, headers=EVENTS).json["item"]
    assert item["registered_count"] == 2 and item["waitlist_count"] == 0


def test_registration_closed_or_off(client):
    off = make(client, title="Just come along")
    assert client.post(f"/me/events/{off['slug']}/register", headers=student(1)).json["error"]["code"] == "registration_off"
    closed = make(client, title="Closed", registration_open=True, start_at=iso(1), registration_closes_at=iso(-1))
    res = client.post(f"/me/events/{closed['slug']}/register", headers=student(1))
    assert res.status_code == 409 and res.json["error"]["code"] == "registration_closed"
    assert client.post(f"/me/events/{off['slug']}/register").status_code == 401


def test_admin_registration_list_csv_and_attendance(client):
    e = make(client, title="Career fair", registration_open=True, capacity=1)
    client.post(f"/me/events/{e['slug']}/register", headers=auth(email="a@ncit.edu.np", name="=HYPERLINK(1)"))
    client.post(f"/me/events/{e['slug']}/register", headers=student(2))
    rows = client.get(f"/events/{e['id']}/registrations", headers=EVENTS).json["items"]
    assert [r["status"] for r in rows] == ["registered", "waitlisted"]
    res = client.patch(f"/events/{e['id']}/registrations/{rows[0]['id']}", json={"attended": True}, headers=EVENTS)
    assert res.json["item"]["attended"] is True
    csv_text = client.get(f"/events/{e['id']}/registrations.csv", headers=EVENTS).get_data(as_text=True)
    assert "'=HYPERLINK(1)" in csv_text and "s2@ncit.edu.np,waitlisted" in csv_text
    client.patch(f"/events/{e['id']}/registrations/{rows[0]['id']}", json={"status": "cancelled"}, headers=EVENTS)
    rows = client.get(f"/events/{e['id']}/registrations", headers=EVENTS).json["items"]
    assert next((r["email"], r["status"]) for r in rows) == ("s2@ncit.edu.np", "registered")


def test_event_rules(client):
    res = client.post("/events", json={"title": "x", "start_at": iso(5), "end_at": iso(4)}, headers=EVENTS)
    assert res.json["error"]["code"] == "invalid_window"
    assert client.post("/events", json={"title": "No date"}, headers=EVENTS).status_code == 422
    a, b = make(client, title="Same name"), make(client, title="Same name")
    assert (a["slug"], b["slug"]) == ("same-name", "same-name-2")


def test_calendar_month(client):
    make(client, title="New year party", start_at="2031-01-01T18:00", end_at="2031-01-01T22:00")
    make(client, title="Late December", start_at="2030-12-31T23:30")  # Nepal time: still December
    jan = client.get("/public/calendar?month=2031-01").json
    assert [i["title"] for i in jan["items"]] == ["New year party"]
    dec = client.get("/public/calendar?month=2030-12").json
    assert [i["title"] for i in dec["items"]] == ["Late December"]
    assert client.get("/public/calendar?month=bad").status_code == 422


def test_upload_programme_pdf(client):
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    res = client.post("/uploads", data={"file": (pdf, "p.pdf"), "kind": "pdf", "group": "events"},
                      headers=EVENTS, content_type="multipart/form-data")
    assert res.status_code == 201 and res.json["url"].startswith("/media/events/events/")
    assert make(client, attachment=res.json["url"])["attachment"] == res.json["url"]


def test_only_college_accounts_can_register(client):
    """Security review: applicants and alumni sign in with any email address; they can't take event places."""
    e = make(client, title="Lab tour", registration_open=True, capacity=1)
    outsider = auth("applicant", email="someone@gmail.com")
    res = client.post(f"/me/events/{e['slug']}/register", headers=outsider)
    assert res.status_code == 403 and res.json["error"]["code"] == "college_account_only"
    assert client.get(f"/public/events/{e['slug']}").json["event"]["registration"]["taken"] == 0
    look_alike = auth(email="student@ncit.edu.np.evil.com")
    assert client.post(f"/me/events/{e['slug']}/register", headers=look_alike).status_code == 403
    assert client.post(f"/me/events/{e['slug']}/register", headers=student(1)).status_code == 201


def test_moving_up_from_the_waiting_list_is_notified(client):
    sent = client.application.config["NOTIFY"].sent
    e = make(client, title="Tiny workshop", registration_open=True, capacity=1)
    for n in (1, 2):
        client.post(f"/me/events/{e['slug']}/register", headers=student(n))
    assert sent == []
    client.delete(f"/me/events/{e['slug']}/register", headers=student(1))
    assert len(sent) == 1 and sent[0]["to"] == "s2@ncit.edu.np" and sent[0]["kind"] == "success"
    assert "Tiny workshop" in sent[0]["title"] and sent[0]["link"] == f"/events/{e['slug']}"
    rows = client.get(f"/events/{e['id']}/registrations", headers=EVENTS).json["items"]
    s2 = next(r for r in rows if r["email"] == "s2@ncit.edu.np")
    client.patch(f"/events/{e['id']}/registrations/{s2['id']}", json={"status": "cancelled"}, headers=EVENTS)
    assert sent[-1]["to"] == "s2@ncit.edu.np" and sent[-1]["kind"] == "warning"
