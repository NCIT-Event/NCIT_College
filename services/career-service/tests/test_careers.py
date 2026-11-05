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
from ncit_common.mail import MemoryMailQueue

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles, email="ada@gmail.com", name="Ada Lovelace"):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": email, "name": name, "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


ADA = auth("applicant")
HR = auth("hr_officer", email="hr@ncit.edu.np")
ADMISSIONS = auth("admission_officer", email="admissions@ncit.edu.np")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def mail():
    return MemoryMailQueue("career-service")


@pytest.fixture
def client(tmp_path, mail):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/c.db", "JWT_PUBLIC_KEY": PUBLIC, "MAIL": mail,
                      "EVENTS": MemoryEventPublisher("career-service"), "MEDIA_ROOT": str(tmp_path / "media"),
                      "PRIVATE_MEDIA_ROOT": str(tmp_path / "private")})
    with app.app_context():
        seed(app.extensions["db"]())
    return app.test_client()


def apply(client, who=ADA, slug="lecturer-computer-engineering", **extra):
    data = {"full_name": "Ada Lovelace", "phone": "9841000000", "qualification": "ME Computer, TU",
            "experience_years": "3", "cover_letter": "I love teaching.", "cv": (io.BytesIO(PDF), "cv.pdf")} | extra
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(f"/me/jobs/{slug}/apply", data=data, headers=who, content_type="multipart/form-data")


def test_public_vacancies(client):
    jobs = client.get("/public/jobs").json["items"]
    assert jobs[0]["slug"] == "it-support-officer"
    assert "application_count" not in jobs[0] and "description" not in jobs[0]
    assert client.get("/public/jobs/lecturer-computer-engineering").json["job"]["requirements"]


def test_apply_review_and_status_emails(client, mail):
    res = apply(client)
    assert res.status_code == 201 and res.json["application"]["status_label"] == "Received"
    assert mail.messages[-1]["template"] == "job_application_received"
    assert apply(client).json["error"]["code"] == "already_applied"
    rows = client.get("/review/applications", headers=HR).json["items"]
    app_id = rows[0]["id"]
    assert client.post(f"/review/applications/{app_id}/status", json={"status": "interview"}, headers=HR).json["error"]["code"] == "message_required"
    client.post(f"/review/applications/{app_id}/status", json={"status": "interview", "message": "Tuesday 11:00, Room 204"}, headers=HR)
    assert mail.messages[-1]["data"] == {"name": "Ada Lovelace", "job": "Lecturer, Computer Engineering",
                                         "status": "interview", "message": "Tuesday 11:00, Room 204"}
    mine = client.get("/me/jobs/lecturer-computer-engineering", headers=ADA).json["application"]
    assert mine["status"] == "interview" and mine["message"] == "Tuesday 11:00, Room 204" and "hr_note" not in mine
    cv = client.get(f"/review/applications/{app_id}/cv", headers=HR)
    assert cv.status_code == 200 and cv.data.startswith(b"%PDF")
    assert "Ada Lovelace" in client.get("/review/applications.csv", headers=HR).get_data(as_text=True)


def test_only_hr_reviews_and_cv_is_required(client):
    assert apply(client, cv=None).json["error"]["code"] in ("invalid_field",)
    apply(client)
    app_id = client.get("/review/applications", headers=HR).json["items"][0]["id"]
    for who in (ADA, ADMISSIONS):
        assert client.get("/review/applications", headers=who).status_code == 403
        assert client.get(f"/review/applications/{app_id}/cv", headers=who).status_code == 403
    assert client.post("/jobs", json={"title": "x"}, headers=ADMISSIONS).status_code == 403
    assert client.get("/me/jobs/lecturer-computer-engineering/cv", headers=auth(email="other@gmail.com")).status_code == 404


def test_closed_and_withdrawn(client):
    jobs = {j["slug"]: j for j in client.get("/jobs", headers=HR).json["items"]}
    client.patch(f"/jobs/{jobs['it-support-officer']['id']}", json={"closes_at": "2020-01-01T10:00"}, headers=HR)
    assert apply(client, slug="it-support-officer").json["error"]["code"] == "closed"
    apply(client)
    assert client.post("/me/jobs/lecturer-computer-engineering/withdraw", headers=ADA).json["application"]["status"] == "withdrawn"
    assert apply(client).status_code == 201  # may apply again after withdrawing
    lecturer = jobs["lecturer-computer-engineering"]["id"]
    assert client.delete(f"/jobs/{lecturer}", headers=HR).json["error"]["code"] == "in_use"
