"""In-app notifications (the bell): who sees what, reading, the API and the worker."""

import json
import os
import time
import uuid

import jwt
import pytest
from app import create_app, inbox
from ncit_common.notify import MemoryNotifier
from test_notifications import PRIVATE, PUBLIC


def token(email, *grants):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": email, "name": email.split("@")[0],
              "roles": [{"role": r, "scope": s} for r, s in grants],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


ADA = token("ada@gmail.com", ("applicant", "*"))
BOB = token("bob@gmail.com", ("applicant", "*"))
OFFICER = token("officer@ncit.edu.np", ("admission_officer", "*"))
CIVIL_HOD = token("civil@ncit.edu.np", ("hod", "dept:civil"))
COMPUTER_HOD = token("computer@ncit.edu.np", ("hod", "dept:computer"))
SUPER = token("admin@ncit.edu.np", ("super_admin", "*"))


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/n.db", "JWT_PUBLIC_KEY": PUBLIC, "SMTP_HOST": ""})


def deliver(app, **kw):
    with app.app_context():
        s = app.extensions["db"]()
        n = inbox.store(s, json.dumps(MemoryNotifier("test").send(**kw)))
        s.commit()
        s.close()
        return n


def titles(client, headers):
    return [n["title"] for n in client.get("/me/notifications", headers=headers).json["items"]]


def test_each_person_sees_only_their_own_and_their_roles(app):
    deliver(app, to="ada@gmail.com", title="Ada: accepted", kind="success", link="/apply")
    deliver(app, role="admission_officer", title="New application", link="/dashboard/#applications")
    deliver(app, role="hod", scope="dept:civil", title="Civil only")
    deliver(app, role="hod", title="All HODs")
    c = app.test_client()
    assert titles(c, ADA) == ["Ada: accepted"]
    assert titles(c, BOB) == []
    assert titles(c, OFFICER) == ["New application"]
    assert sorted(titles(c, CIVIL_HOD)) == ["All HODs", "Civil only"]
    assert titles(c, COMPUTER_HOD) == ["All HODs"]
    assert titles(c, SUPER) == []  # not flooded with every role's notifications
    first = c.get("/me/notifications", headers=ADA).json
    assert first["unread"] == 1 and first["items"][0]["link"] == "/apply" and first["items"][0]["read"] is False
    assert first["items"][0]["kind"] == "success"


def test_reading_affects_only_yourself(app):
    n = deliver(app, role="hod", title="All HODs")
    mine = deliver(app, to="ada@gmail.com", title="Ada's")
    c = app.test_client()
    # Bob can't mark Ada's notification read, and marking one he can't see does nothing
    assert c.post("/me/notifications/read", json={"ids": [mine.id]}, headers=BOB).json["marked"] == 0
    assert c.get("/me/notifications/unread", headers=ADA).json["unread"] == 1
    # one HOD reading a role notification doesn't read it for the other
    assert c.post("/me/notifications/read", json={"ids": [n.id]}, headers=CIVIL_HOD).json == {"marked": 1, "unread": 0}
    assert c.get("/me/notifications/unread", headers=COMPUTER_HOD).json["unread"] == 1
    assert c.post("/me/notifications/read", json={"all": True}, headers=ADA).json["unread"] == 0
    assert c.get("/me/notifications", headers=ADA).json["items"][0]["read"] is True
    assert c.post("/me/notifications/read", json={"all": True}, headers=ADA).json["marked"] == 0


def test_the_bell_needs_a_sign_in_and_a_csrf_token(app):
    c = app.test_client()
    assert c.get("/me/notifications").status_code == 401
    assert c.get("/me/notifications/unread").status_code == 401
    assert c.post("/me/notifications/read", json={"all": True}).status_code == 401
    raw = ADA["Authorization"].split(" ", 1)[1]
    c.set_cookie("ncit_access", raw)
    assert c.get("/me/notifications/unread").status_code == 200
    assert c.post("/me/notifications/read", json={"all": True}).status_code == 403  # cookie without CSRF token
    assert c.get("/me/notifications", headers=ADA).headers["Cache-Control"] == "private, no-store"
    assert c.post("/me/notifications/read", json={"ids": "x"}, headers=ADA).status_code == 422
    assert c.get("/me/notifications?page=x", headers=ADA).status_code == 422


def test_paging_storage_rules_and_pruning(app):
    for i in range(12):
        deliver(app, to="ada@gmail.com", title=f"n{i}", link="https://evil.example/x")
    c = app.test_client()
    page1 = c.get("/me/notifications?per_page=10", headers=ADA).json
    assert len(page1["items"]) == 10 and page1["more"] is True and page1["items"][0]["link"] == ""
    assert len(c.get("/me/notifications?per_page=10&page=2", headers=ADA).json["items"]) == 2
    # the same queued notification is stored once
    note = MemoryNotifier("t").send(to="ada@gmail.com", title="once")
    with app.app_context():
        s = app.extensions["db"]()
        assert inbox.store(s, json.dumps(note)) is not None
        s.commit()
        assert inbox.store(s, json.dumps(note)) is None
        from datetime import timedelta

        from app.models import Notification, utcnow
        old = s.query(Notification).filter_by(title="n0").one()
        old.created_at = utcnow() - timedelta(days=inbox.KEEP_DAYS + 1)
        s.commit()
        assert inbox.prune(s) == 1
        s.commit()


def test_worker_stores_notifications_and_mail_together(app):
    redis = pytest.importorskip("redis")
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("set TEST_REDIS_URL to run the worker against Redis")
    from app.worker import GROUP, ensure_group, process_batch
    from ncit_common.mail import MAIL_STREAM, MailQueue
    from ncit_common.notify import NOTIFY_STREAM, Notifier
    from test_notifications import FakeSmtp

    r = redis.Redis.from_url(url, decode_responses=True)
    r.delete(MAIL_STREAM, NOTIFY_STREAM)
    ensure_group(r)
    Notifier(r, "test").send(to="ada@gmail.com", title="Your application: Accepted", link="/apply")
    MailQueue(r, "test").send("ada@gmail.com", "job_application_received", {"name": "Ada", "job": "Lecturer"})
    assert process_batch(r, app.extensions["db"], "t1", FakeSmtp(), block_ms=100) == 2
    assert titles(app.test_client(), ADA) == ["Your application: Accepted"]
    assert r.xpending(NOTIFY_STREAM, GROUP)["pending"] == 0
    r.delete(MAIL_STREAM, NOTIFY_STREAM)
