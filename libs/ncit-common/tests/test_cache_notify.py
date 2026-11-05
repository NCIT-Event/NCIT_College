"""The Redis public-page cache and the notification queue."""

import pytest
from flask import Blueprint, Flask, jsonify, make_response
from ncit_common import register_error_handlers
from ncit_common.cache import MemoryPublicCache, PublicCache, init_public_cache
from ncit_common.notify import MemoryNotifier, clean_link


def make_app(cache):
    app = Flask(__name__)
    register_error_handlers(app)
    state = {"news": ["first"], "reads": 0}
    public, me = Blueprint("public", __name__, url_prefix="/public"), Blueprint("me", __name__, url_prefix="/me")

    @public.get("/news")
    def news():
        state["reads"] += 1
        return jsonify(items=state["news"])

    @public.get("/with-cookie")
    def with_cookie():
        state["reads"] += 1
        resp = make_response(jsonify(ok=True))
        resp.set_cookie("x", "1")
        return resp

    @me.get("/mine")
    def mine():
        state["reads"] += 1
        return jsonify(items=["private"])

    @app.post("/news")
    def add():
        state["news"].append("second")
        return jsonify(ok=True), 201

    @app.post("/refused")
    def refused():
        return jsonify(error="no"), 403

    app.register_blueprint(public)
    app.register_blueprint(me)
    init_public_cache(app, cache)
    return app, state


@pytest.fixture
def setup():
    cache = MemoryPublicCache("test")
    app, state = make_app(cache)
    return app.test_client(), state, cache


def test_public_answers_come_from_the_cache(setup):
    client, state, _ = setup
    first = client.get("/public/news")
    assert first.headers["X-App-Cache"] == "MISS" and state["reads"] == 1
    second = client.get("/public/news")
    assert second.headers["X-App-Cache"] == "HIT" and second.json == first.json and state["reads"] == 1
    assert second.mimetype == "application/json"


def test_a_change_shows_at_once(setup):
    client, *_ = setup
    client.get("/public/news")
    assert client.post("/news").status_code == 201
    fresh = client.get("/public/news")
    assert fresh.headers["X-App-Cache"] == "MISS" and fresh.json["items"] == ["first", "second"]


def test_a_refused_change_keeps_the_cache(setup):
    client, *_ = setup
    client.get("/public/news")
    client.post("/refused")
    assert client.get("/public/news").headers["X-App-Cache"] == "HIT"


def test_signed_in_and_cookie_answers_are_never_cached(setup):
    client, state, _ = setup
    for _ in range(2):
        assert "X-App-Cache" not in client.get("/me/mine").headers
    assert state["reads"] == 2
    client.get("/public/with-cookie")
    client.get("/public/with-cookie")
    assert state["reads"] == 4  # a response that sets a cookie is never shared


def test_query_order_and_long_queries(setup):
    client, state, _ = setup
    client.get("/public/news?a=1&b=2")
    assert client.get("/public/news?b=2&a=1").headers["X-App-Cache"] == "HIT"
    long = "/public/news?q=" + "x" * 400
    client.get(long)
    client.get(long)
    assert state["reads"] == 3  # not cached: junk queries can't fill the cache


def test_cache_expires(setup, monkeypatch):
    client, _, cache = setup
    client.get("/public/news")
    import time
    real = time.time
    monkeypatch.setattr("ncit_common.cache.time.time", lambda: real() + cache.ttl + 1)
    assert client.get("/public/news").headers["X-App-Cache"] == "MISS"


class BrokenRedis:
    def get(self, *a, **k):
        raise ConnectionError("redis is down")

    set = get


def test_redis_down_means_answers_from_the_database():
    app, state = make_app(PublicCache(BrokenRedis(), "test"))
    client = app.test_client()
    assert client.get("/public/news").status_code == 200
    assert client.get("/public/news").status_code == 200 and state["reads"] == 2
    assert client.post("/news").status_code == 201


def test_notifications_are_validated():
    n = MemoryNotifier("svc")
    note = n.send(to="Ada@Gmail.com", title="  Your   application  ", link="/apply", kind="success")
    assert note["to"] == "ada@gmail.com" and note["title"] == "Your application" and note["role"] == ""
    assert n.send(role="hod", scope="dept:civil", title="x")["scope"] == "dept:civil"
    with pytest.raises(ValueError):
        n.send(title="nobody")
    assert n.send(to="a@b.c", title="x", kind="weird")["kind"] == "info"
    for bad in ("https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "/a b"):
        assert clean_link(bad) == "", bad
    assert clean_link("/dashboard/#applications/1") == "/dashboard/#applications/1"
