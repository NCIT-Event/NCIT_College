from app import create_app


def test_health():
    client = create_app().test_client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json["status"] == "ok"


def test_ready_needs_database():
    assert create_app({"DATABASE_URL": ""}).test_client().get("/ready").status_code == 503
    app = create_app({"DATABASE_URL": "postgresql://x"})
    assert app.test_client().get("/ready").status_code == 200


def test_errors_use_shared_shape():
    res = create_app().test_client().get("/nope")
    assert res.status_code == 404
    assert res.json["error"]["code"] == "not_found"
