import json
import time
import uuid

import jwt
import pytest
from app import create_app
from app.delivery import REDACTED, deliver
from app.models import Message
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ncit_common.mail import MemoryMailQueue

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": "x@ncit.edu.np", "name": "X", "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


class FakeSmtp:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, to, subject, body):
        if self.fail:
            raise ConnectionRefusedError("mail server down")
        self.sent.append((to, subject, body))


def queued(template, data, sensitive=False, to="ada@gmail.com"):
    return json.dumps(MemoryMailQueue("test").send(to, template, data, sensitive=sensitive))


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/n.db", "JWT_PUBLIC_KEY": PUBLIC, "SMTP_HOST": ""})


@pytest.fixture
def session(app):
    return app.extensions["db"]()


def test_status_email_is_rendered_and_sent(session):
    smtp = FakeSmtp()
    m = deliver(session, queued("application_status", {"name": "Ada", "status": "accepted", "reference": "NCIT-2026-00001",
                                                       "programme": "BE Computer Engineering", "message": "Bring your documents."}), smtp)
    session.commit()
    assert m.status == "sent" and smtp.sent[0][0] == "ada@gmail.com"
    assert "offered a place" in m.subject and "Bring your documents." in m.body and "NCIT-2026-00001" in m.body


def test_sign_in_codes_are_not_kept(session):
    smtp = FakeSmtp()
    m = deliver(session, queued("sign_in_code", {"code": "482913", "purpose": "applicant"}, sensitive=True), smtp)
    assert "482913" in smtp.sent[0][2] and "482913" in smtp.sent[0][1]
    assert m.body == REDACTED and "482913" not in m.body + m.subject
    kept = deliver(session, queued("sign_in_code", {"code": "111222"}, sensitive=True), smtp, keep_sensitive=True)
    assert "111222" in kept.body  # local development only


def test_same_message_twice_is_sent_once(session):
    smtp = FakeSmtp()
    raw = queued("job_application_received", {"name": "Ada", "job": "Lecturer"})
    deliver(session, raw, smtp)
    session.commit()
    deliver(session, raw, smtp)
    assert len(smtp.sent) == 1


def test_failures_are_logged_and_can_be_retried(app, session):
    m = deliver(session, queued("alumni_status", {"name": "Ram", "status": "verified", "listed": True}), FakeSmtp(fail=True))
    session.commit()
    assert m.status == "failed" and "mail server down" in m.error
    unknown = deliver(session, queued("nope", {}), FakeSmtp())
    session.commit()
    assert unknown.status == "failed" and "unknown email template" in unknown.error

    client = app.test_client()
    log = client.get("/messages", headers=auth("super_admin")).json
    assert log["counts"]["failed"] == 2 and log["smtp"] is False
    assert client.get("/messages", headers=auth("content_admin")).status_code == 403
    res = client.post(f"/messages/{m.id}/retry", headers=auth("super_admin"))
    assert res.json["item"]["status"] == "logged"  # no SMTP_HOST here: logged instead of sent
    assert client.post(f"/messages/{m.id}/retry", headers=auth("super_admin")).status_code == 409
    assert "directory" in client.get(f"/messages/{m.id}", headers=auth("super_admin")).json["item"]["body"]


def test_every_template_renders():
    from app.templates import TEMPLATES, render

    data = {"code": "123456", "name": "A", "reference": "R", "programme": "P", "intake": "I", "status": "accepted",
            "job": "J", "message": "M", "listed": True, "topic": "T", "email": "e@x.com", "phone": ""}
    for name in TEMPLATES:
        subject, body = render(name, data)
        assert subject and "ncit" in body.lower()
    assert Message.__tablename__ == "messages"


def test_worker_consumes_the_mail_stream(app, session):
    import os

    redis = pytest.importorskip("redis")
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("set TEST_REDIS_URL to run the worker against Redis")
    from app.worker import GROUP, ensure_group, process_batch
    from ncit_common.mail import MAIL_STREAM, MailQueue

    r = redis.Redis.from_url(url, decode_responses=True)
    r.delete(MAIL_STREAM, "ncit:notify")
    ensure_group(r)
    MailQueue(r, "test").send("ada@gmail.com", "job_application_received", {"name": "Ada", "job": "Lecturer"})
    smtp = FakeSmtp()
    assert process_batch(r, app.extensions["db"], "t1", smtp, block_ms=100) == 1
    assert smtp.sent[0][1] == "Application received: Lecturer"
    assert r.xpending(MAIL_STREAM, GROUP)["pending"] == 0
    r.delete(MAIL_STREAM)


def test_subject_is_always_one_line():
    """Security review: a Contact-form name with line breaks must not break (or inject into) the email header."""
    from email.message import EmailMessage

    from app.templates import render

    subject, body = render("contact_message", {"topic": "Admissions", "name": "Bob\r\nBcc: victim@example.com\x00",
                                               "email": "bob@example.com", "phone": "", "message": "Hello there"})
    assert "\r" not in subject and "\n" not in subject and "\x00" not in subject
    assert subject == "Website enquiry (Admissions): Bob Bcc: victim@example.com"
    EmailMessage()["Subject"] = subject  # would raise if a line break got through
    assert "Hello there" in body
