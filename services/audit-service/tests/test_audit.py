import json
import os
import time
import uuid

import jwt
import pytest
from app import create_app
from app.ingest import store_event
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ncit_common import MemoryEventPublisher

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def token(roles):
    now = time.time()
    return jwt.encode({"sub": "u1", "email": "admin@ncit.edu.np", "roles": roles, "jti": uuid.uuid4().hex,
                       "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"},
                      PRIVATE, algorithm="RS256")


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/audit.db", "JWT_PUBLIC_KEY": PUBLIC})


def add_events(app, *types):
    pub = MemoryEventPublisher("auth-service")
    for t in types:
        pub.publish(t, actor={"id": "a1", "email": "admin@ncit.edu.np"}, entity="user", entity_id="u2",
                    data={"role": "hod"}, ip="10.0.0.1")
    with app.app_context():
        s = app.extensions["db"]()
        for e in pub.events:
            store_event(s, json.dumps(e))
        s.commit()
    return pub.events


def test_store_event_is_idempotent(app):
    ev = add_events(app, "role.granted")[0]
    with app.app_context():
        s = app.extensions["db"]()
        assert store_event(s, ev) is False


def test_only_super_admin_reads_the_log(app):
    add_events(app, "role.granted")
    c = app.test_client()
    assert c.get("/").status_code == 401
    assert c.get("/", headers={"Authorization": f"Bearer {token([{'role': 'hod', 'scope': 'dept:civil'}])}"}).status_code == 403
    res = c.get("/", headers={"Authorization": f"Bearer {token([{'role': 'super_admin', 'scope': '*'}])}"})
    assert res.status_code == 200 and res.json["total"] == 1
    assert res.json["items"][0]["actor"]["email"] == "admin@ncit.edu.np"


def test_filter_by_type_prefix(app):
    add_events(app, "role.granted", "role.revoked", "user.signed_in")
    h = {"Authorization": f"Bearer {token([{'role': 'super_admin', 'scope': '*'}])}"}
    assert app.test_client().get("/?type=role.", headers=h).json["total"] == 2


@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="set TEST_REDIS_URL to run against Redis")
def test_worker_consumes_stream(app):
    import redis
    from app import worker
    from ncit_common.events import EventPublisher

    r = redis.Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    r.delete("ncit:events")
    worker.ensure_group(r)
    EventPublisher(r, "auth-service").publish("role.granted", actor={"id": "a"}, entity="user", entity_id="u")
    Session = app.extensions["db"]
    assert worker.process_batch(r, Session, "test", block_ms=100) == 1
    assert r.xpending("ncit:events", "audit")["pending"] == 0
