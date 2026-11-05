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


RAM = auth("alumni", email="ram.alum@gmail.com", name="Ram Shrestha")
SITA = auth("alumni", email="sita.alum@gmail.com", name="Sita")
COORD = auth("alumni_coordinator", email="alumni@ncit.edu.np")
HR = auth("hr_officer", email="hr@ncit.edu.np")
DETAILS = {"full_name": "Ram Shrestha", "programme": "BE Computer Engineering", "graduation_year": "2016",
           "registration_no": "2012-1-32-0456", "current_role": "Backend engineer", "employer": "Fusemachines",
           "city": "Kathmandu", "linkedin_url": "https://www.linkedin.com/in/ram", "show_in_directory": True}


@pytest.fixture
def mail():
    return MemoryMailQueue("alumni-service")


@pytest.fixture
def client(tmp_path, mail):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/al.db", "JWT_PUBLIC_KEY": PUBLIC, "MAIL": mail,
                      "EVENTS": MemoryEventPublisher("alumni-service"), "MEDIA_ROOT": str(tmp_path / "media")})
    with app.app_context():
        seed(app.extensions["db"]())
    return app.test_client()


def register(client, who=RAM, **extra):
    assert client.put("/me/profile", json=DETAILS | extra, headers=who).status_code == 200
    return client.post("/me/profile/submit", headers=who)


def names(client, path="/public/directory"):
    return [a["full_name"] for a in client.get(path).json["items"]]


def test_gate_alumni_verification(client, mail):
    """Phase 5 gate (alumni): register, the coordinator verifies, the alumnus is emailed and listed."""
    res = register(client)
    assert res.json["profile"]["status"] == "pending"
    assert "Ram Shrestha" not in names(client)
    queue = client.get("/review/profiles?status=pending", headers=COORD).json["items"]
    assert [p["registration_no"] for p in queue] == ["2012-1-32-0456"]
    client.post(f"/review/profiles/{queue[0]['id']}/status", json={"status": "verified"}, headers=COORD)
    assert mail.messages[-1]["template"] == "alumni_status" and mail.messages[-1]["data"]["status"] == "verified"
    assert mail.messages[-1]["to"] == "ram.alum@gmail.com"
    card = next(a for a in client.get("/public/directory").json["items"] if a["full_name"] == "Ram Shrestha")
    assert card["employer"] == "Fusemachines" and "email" not in card and "phone" not in card and "registration_no" not in card
    assert client.get("/me/profile", headers=RAM).json["profile"]["status_label"] == "Verified"


def test_rejection_needs_a_reason_and_can_be_corrected(client, mail):
    register(client)
    pid = client.get("/review/profiles", headers=COORD).json["items"][0]["id"]
    assert client.post(f"/review/profiles/{pid}/status", json={"status": "rejected"}, headers=COORD).status_code == 422
    client.post(f"/review/profiles/{pid}/status", json={"status": "rejected", "message": "Registration number not found."}, headers=COORD)
    mine = client.get("/me/profile", headers=RAM).json["profile"]
    assert mine["status"] == "rejected" and mine["review_note"] == "Registration number not found."
    assert mail.messages[-1]["data"]["message"] == "Registration number not found."
    assert client.post("/me/profile/submit", headers=RAM).json["profile"]["status"] == "pending"


def test_changing_checked_details_needs_verifying_again(client):
    register(client)
    pid = client.get("/review/profiles", headers=COORD).json["items"][0]["id"]
    client.post(f"/review/profiles/{pid}/status", json={"status": "verified"}, headers=COORD)
    client.patch(f"/review/profiles/{pid}", json={"featured": True}, headers=COORD)
    assert "Ram Shrestha" in names(client, "/public/featured")
    p = client.put("/me/profile", json={"employer": "Leapfrog"}, headers=RAM).json["profile"]
    assert p["status"] == "verified"  # job changes don't need re-checking
    p = client.put("/me/profile", json={"graduation_year": "2017"}, headers=RAM).json["profile"]
    assert p["status"] == "pending" and "Ram Shrestha" not in names(client)
    assert "Ram Shrestha" not in names(client, "/public/featured")


def test_privacy_and_roles(client):
    register(client, show_in_directory=False)
    pid = client.get("/review/profiles", headers=COORD).json["items"][0]["id"]
    client.post(f"/review/profiles/{pid}/status", json={"status": "verified"}, headers=COORD)
    assert "Ram Shrestha" not in names(client)  # verified, but didn't agree to be listed
    assert client.patch(f"/review/profiles/{pid}", json={"featured": True}, headers=COORD).json["error"]["code"] == "not_listed"
    for who in (RAM, HR):
        assert client.get("/review/profiles", headers=who).status_code == 403
        assert client.post(f"/review/profiles/{pid}/status", json={"status": "rejected", "message": "x"}, headers=who).status_code == 403
    assert client.get("/me/profile", headers=SITA).json["profile"] is None


def test_validation(client):
    bad = client.put("/me/profile", json={"graduation_year": "1995"}, headers=SITA)
    assert bad.json["error"]["code"] == "invalid_field"
    assert client.put("/me/profile", json={"linkedin_url": "https://evil.example/in/x"}, headers=SITA).status_code == 422
    client.put("/me/profile", json={"full_name": "Sita"}, headers=SITA)
    res = client.post("/me/profile/submit", headers=SITA)
    assert res.json["error"]["code"] == "incomplete" and "Programme" in res.json["error"]["message"]
    assert len(client.get("/public/featured").json["items"]) == 4  # the seeded samples
