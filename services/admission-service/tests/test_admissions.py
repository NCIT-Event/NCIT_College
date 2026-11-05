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
from PIL import Image

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUBLIC = _key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def auth(*roles, email="ada@gmail.com", name="Ada Lovelace"):
    now = time.time()
    claims = {"sub": uuid.uuid4().hex, "email": email, "name": name, "roles": [{"role": r, "scope": "*"} for r in roles],
              "jti": uuid.uuid4().hex, "iat": now, "exp": int(now + 600), "iss": "ncit-auth", "aud": "ncit-web"}
    return {"Authorization": f"Bearer {jwt.encode(claims, PRIVATE, algorithm='RS256')}"}


ADA = auth("applicant")
BOB = auth("applicant", email="bob@yahoo.com", name="Bob")
OFFICER = auth("admission_officer", email="admissions@ncit.edu.np")
HR = auth("hr_officer", email="hr@ncit.edu.np")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
DETAILS = {"second_choice_id": "", "full_name": "Ada Lovelace", "date_of_birth": "2007-04-15", "gender": "female", "phone": "9841000000",
           "address": "Balkumari, Lalitpur", "guardian_name": "Anne Lovelace", "guardian_phone": "9841000001",
           "school": "Kathmandu Model College", "board": "NEB", "passed_year": "2025", "grade": "3.6"}


@pytest.fixture
def mail():
    return MemoryMailQueue("admission-service")


@pytest.fixture
def events():
    return MemoryEventPublisher("admission-service")


@pytest.fixture
def client(tmp_path, mail, events):
    app = create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/a.db", "JWT_PUBLIC_KEY": PUBLIC, "MAIL": mail, "EVENTS": events,
                      "MEDIA_ROOT": str(tmp_path / "media"), "PRIVATE_MEDIA_ROOT": str(tmp_path / "private")})
    with app.app_context():
        seed(app.extensions["db"]())
    c = app.test_client()
    c.tmp = tmp_path
    return c


def programmes(client):
    intake = client.get("/public/intakes").json["items"][0]
    return intake, {o["programme"]: o["id"] for o in intake["offerings"]}


def photo():
    buf = io.BytesIO()
    Image.new("RGB", (400, 500), "white").save(buf, "JPEG")
    return io.BytesIO(buf.getvalue())


def complete_application(client, who=ADA, programme="BE Computer Engineering"):
    _, prog = programmes(client)
    app = client.post("/me/applications", json={"offering_id": prog[programme]}, headers=who).json["item"]
    assert client.patch(f"/me/applications/{app['id']}", json=DETAILS, headers=who).status_code == 200
    for doc, data, name in (("photo", photo(), "p.jpg"), ("transcript", io.BytesIO(PDF), "t.pdf")):
        res = client.post(f"/me/applications/{app['id']}/documents/{doc}", data={"file": (data, name)}, headers=who,
                          content_type="multipart/form-data")
        assert res.status_code == 200, res.json
    return app["id"]


def test_public_intake_lists_programmes(client):
    intake, prog = programmes(client)
    assert intake["name"] == "Fall 2026" and intake["status"] == "open" and len(prog) == 8
    assert "published" not in intake["offerings"][0]


def test_gate_apply_review_and_status_email(client, mail, events):
    """Phase 5 gate (admissions): apply, the office reviews, and the applicant is emailed at each step."""
    app_id = complete_application(client)
    sent = client.post(f"/me/applications/{app_id}/submit", headers=ADA).json["item"]
    assert sent["status"] == "submitted" and sent["reference"].startswith("NCIT-") and not sent["editable"]
    assert mail.messages[-1]["template"] == "application_submitted" and mail.messages[-1]["to"] == "ada@gmail.com"
    assert mail.messages[-1]["data"]["reference"] == sent["reference"]

    rows = client.get("/review/applications", headers=OFFICER).json
    assert rows["items"][0]["reference"] == sent["reference"] and rows["counts"] == {"submitted": 1}
    client.post(f"/review/applications/{app_id}/status", json={"status": "under_review"}, headers=OFFICER)
    res = client.post(f"/review/applications/{app_id}/status",
                      json={"status": "accepted", "message": "Fee payment opens on 1 December."}, headers=OFFICER)
    assert res.json["item"]["status"] == "accepted"
    last = mail.messages[-1]
    assert last["template"] == "application_status" and last["data"]["status"] == "accepted"
    assert last["data"]["message"] == "Fee payment opens on 1 December."
    assert [m["data"].get("status") for m in mail.messages] == [None, "under_review", "accepted"]

    mine = client.get(f"/me/applications/{app_id}", headers=ADA).json["item"]
    assert mine["status_label"] == "Accepted" and mine["message"] == "Fee payment opens on 1 December."
    assert [h["status"] for h in mine["history"]] == ["submitted", "under_review", "accepted"]
    assert "by" not in mine["history"][0] and "officer_note" not in mine
    assert "applications.accepted" in [e["type"] for e in events.events]


def test_more_documents_requested_then_resubmitted(client, mail):
    app_id = complete_application(client)
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    no_msg = client.post(f"/review/applications/{app_id}/status", json={"status": "documents_requested"}, headers=OFFICER)
    assert no_msg.json["error"]["code"] == "message_required"
    client.post(f"/review/applications/{app_id}/status", json={"status": "documents_requested",
                                                               "message": "Upload your citizenship."}, headers=OFFICER)
    mine = client.get(f"/me/applications/{app_id}", headers=ADA).json["item"]
    assert mine["editable"] and mine["message"] == "Upload your citizenship."
    client.post(f"/me/applications/{app_id}/documents/citizenship", data={"file": (io.BytesIO(PDF), "c.pdf")},
                headers=ADA, content_type="multipart/form-data")
    again = client.post(f"/me/applications/{app_id}/submit", headers=ADA).json["item"]
    assert again["status"] == "submitted" and again["documents"]["citizenship"]
    assert [m["template"] for m in mail.messages].count("application_submitted") == 1  # only the first time


def test_incomplete_or_invalid_applications(client):
    _, prog = programmes(client)
    app = client.post("/me/applications", json={"offering_id": prog["BE Civil Engineering"]}, headers=ADA).json["item"]
    res = client.post(f"/me/applications/{app['id']}/submit", headers=ADA)
    assert res.json["error"]["code"] == "incomplete" and "Academic transcript" in res.json["error"]["message"]
    bad = client.patch(f"/me/applications/{app['id']}", json={"date_of_birth": "15/04/2007"}, headers=ADA)
    assert bad.status_code == 422
    assert client.patch(f"/me/applications/{app['id']}", json={"status": "accepted"}, headers=ADA).status_code == 422
    again = client.post("/me/applications", json={"offering_id": prog["BE Civil Engineering"]}, headers=ADA)
    assert again.json["error"]["code"] == "already_applied"
    fake = client.post(f"/me/applications/{app['id']}/documents/transcript", data={"file": (io.BytesIO(b"nope"), "t.pdf")},
                       headers=ADA, content_type="multipart/form-data")
    assert fake.json["error"]["code"] == "not_a_pdf"


def test_applicants_see_only_their_own_and_documents_are_private(client):
    app_id = complete_application(client)
    assert client.get(f"/me/applications/{app_id}", headers=BOB).status_code == 404
    assert client.get(f"/me/applications/{app_id}/documents/transcript", headers=BOB).status_code == 404
    own = client.get(f"/me/applications/{app_id}/documents/transcript", headers=ADA)
    assert own.status_code == 200 and own.data.startswith(b"%PDF") and own.headers["Cache-Control"] == "private, no-store"
    assert not (client.tmp / "media").exists() or not any((client.tmp / "media").rglob("*.pdf"))
    # the office sees documents only after the application is sent
    assert client.get(f"/review/applications/{app_id}/documents/transcript", headers=OFFICER).status_code == 404
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    assert client.get(f"/review/applications/{app_id}/documents/transcript", headers=OFFICER).status_code == 200


def test_only_admission_officers_review(client):
    app_id = complete_application(client)
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    for who in (ADA, HR):
        assert client.get("/review/applications", headers=who).status_code == 403
        assert client.post(f"/review/applications/{app_id}/status", json={"status": "accepted"}, headers=who).status_code == 403
    assert client.post("/intakes", json={"name": "x"}, headers=HR).status_code == 403


def test_status_moves_are_checked_and_withdrawal(client):
    app_id = complete_application(client)
    assert client.post(f"/review/applications/{app_id}/status", json={"status": "accepted"}, headers=OFFICER).status_code == 404
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    res = client.post(f"/review/applications/{app_id}/status", json={"status": "submitted"}, headers=OFFICER)
    assert res.json["error"]["code"] == "invalid_move"
    assert client.post(f"/me/applications/{app_id}/withdraw", headers=ADA).json["item"]["status"] == "withdrawn"
    res = client.post(f"/review/applications/{app_id}/status", json={"status": "accepted"}, headers=OFFICER)
    assert res.status_code == 409


def test_closed_intake_and_csv(client):
    app_id = complete_application(client)
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    csv_text = client.get("/review/applications.csv", headers=OFFICER).get_data(as_text=True)
    assert "Ada Lovelace" in csv_text and "BE Computer Engineering" in csv_text
    intake, prog = programmes(client)
    client.patch(f"/intakes/{intake['id']}", json={"closes_at": "2020-01-02T00:00", "opens_at": "2020-01-01T00:00"},
                 headers=OFFICER)
    assert client.get("/public/intakes").json["items"] == []
    res = client.post("/me/applications", json={"offering_id": prog["BE Civil Engineering"]}, headers=BOB)
    assert res.json["error"]["code"] == "intake_closed"
    assert client.delete(f"/intakes/{intake['id']}", headers=OFFICER).json["error"]["code"] == "in_use"


def test_replacing_a_document_deletes_the_old_file(client):
    """Security review: an applicant's replaced transcript must not stay on disk."""
    _, prog = programmes(client)
    app = client.post("/me/applications", json={"offering_id": prog["BE Civil Engineering"]}, headers=ADA).json["item"]
    folder = client.tmp / "private" / "admissions" / "documents"
    for _ in range(3):
        res = client.post(f"/me/applications/{app['id']}/documents/transcript",
                          data={"file": (io.BytesIO(PDF), "t.pdf")}, headers=ADA, content_type="multipart/form-data")
        assert res.status_code == 200
    assert len(list(folder.glob("*.pdf"))) == 1
    assert client.get(f"/me/applications/{app['id']}/documents/transcript", headers=ADA).status_code == 200


def test_bell_notifications_for_the_office_and_the_applicant(client):
    sent = client.application.config["NOTIFY"].sent
    app_id = complete_application(client)
    client.post(f"/me/applications/{app_id}/submit", headers=ADA)
    office = sent[-1]
    assert office["role"] == "admission_officer" and office["to"] == "" and office["kind"] == "action"
    assert office["title"].startswith("New application") and office["link"] == f"/dashboard/#applications/{app_id}"
    client.post(f"/review/applications/{app_id}/status", json={"status": "under_review"}, headers=OFFICER)
    client.post(f"/review/applications/{app_id}/status", json={"status": "accepted", "message": "Welcome!"}, headers=OFFICER)
    mine = sent[-1]
    assert mine["to"] == "ada@gmail.com" and mine["title"] == "Your application: Accepted"
    assert mine["kind"] == "success" and mine["body"] == "Welcome!" and mine["link"] == "/apply"
    before = len(sent)
    client.post(f"/review/applications/{app_id}/status", json={"status": "waitlisted", "notify": False}, headers=OFFICER)
    assert len(sent) == before  # a quiet correction tells nobody
