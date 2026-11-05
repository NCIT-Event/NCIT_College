import re

import pytest
from conftest import csrf, google_sign_in
from ncit_common.mail import MemoryMailQueue


@pytest.fixture
def mail(app):
    q = MemoryMailQueue("auth-service")
    app.config["MAIL"] = q
    return q


def last_code(mail):
    return mail.messages[-1]["data"]["code"]


def test_applicant_signs_in_with_emailed_code(client, mail, events):
    res = client.post("/code/request", json={"email": "Ada.Applicant@Gmail.com", "purpose": "applicant"})
    assert res.status_code == 200 and res.json["sent_to"] == "ada.applicant@gmail.com"
    assert "dev_code" not in res.json  # only with DEV_LOGIN
    msg = mail.messages[0]
    assert msg["to"] == "ada.applicant@gmail.com" and msg["sensitive"] is True and re.fullmatch(r"\d{6}", msg["data"]["code"])

    res = client.post("/code/verify", json={"email": "ada.applicant@gmail.com", "code": last_code(mail), "name": "Ada Lovelace"})
    assert res.status_code == 200
    user = res.json["user"]
    assert user["kind"] == "external" and [r["role"] for r in user["roles"]] == ["applicant"]
    assert user["roles"][0]["role_name"] == "Applicant" and user["name"] == "Ada Lovelace"
    me = client.get("/me").json["user"]
    assert me["email"] == "ada.applicant@gmail.com"
    # the code never reaches the audit stream
    assert not any("code" in e["data"] for e in events.events)
    assert [e["data"].get("method") for e in events.events if e["type"] == "user.signed_in"] == ["email_code"]


def test_code_works_once_and_wrong_codes_run_out(client, mail):
    client.post("/code/request", json={"email": "bob@yahoo.com", "purpose": "alumni"})
    code = last_code(mail)
    wrong = "000000" if code != "000000" else "111111"
    for left in (4, 3, 2, 1):
        res = client.post("/code/verify", json={"email": "bob@yahoo.com", "code": wrong})
        assert res.json["error"]["code"] == "wrong_code" and f"{left} " in res.json["error"]["message"]
    res = client.post("/code/verify", json={"email": "bob@yahoo.com", "code": wrong})
    assert res.json["error"]["code"] == "code_expired"
    # even the right code is dead now
    assert client.post("/code/verify", json={"email": "bob@yahoo.com", "code": code}).json["error"]["code"] == "code_expired"
    client.post("/code/request", json={"email": "bob@yahoo.com", "purpose": "alumni"})
    code = last_code(mail)
    assert client.post("/code/verify", json={"email": "bob@yahoo.com", "code": code}).status_code == 200
    assert client.post("/code/verify", json={"email": "bob@yahoo.com", "code": code}).json["error"]["code"] == "code_expired"


def test_college_addresses_and_bad_input_are_refused(client, mail):
    res = client.post("/code/request", json={"email": "someone@ncit.edu.np", "purpose": "applicant"})
    assert res.json["error"]["code"] == "use_google"
    assert client.post("/code/request", json={"email": "not-an-email", "purpose": "applicant"}).status_code == 422
    assert client.post("/code/request", json={"email": "a@b.com", "purpose": "super_admin"}).json["error"]["code"] == "invalid_purpose"
    assert mail.messages == []


def test_too_many_codes(client, mail):
    for _ in range(3):
        assert client.post("/code/request", json={"email": "spam@b.com", "purpose": "applicant"}).status_code == 200
    res = client.post("/code/request", json={"email": "spam@b.com", "purpose": "applicant"})
    assert res.status_code == 429 and len(mail.messages) == 3


def test_external_accounts_get_no_dashboard_roles_and_stay_out_of_users_list(app, client, mail, google):
    client.post("/code/request", json={"email": "alum@gmail.com", "purpose": "alumni"})
    client.post("/code/verify", json={"email": "alum@gmail.com", "code": last_code(mail)})
    client.post("/code/request", json={"email": "alum@gmail.com", "purpose": "applicant"})
    roles = client.post("/code/verify", json={"email": "alum@gmail.com", "code": last_code(mail)}).json["user"]["roles"]
    assert sorted(r["role"] for r in roles) == ["alumni", "applicant"]
    assert client.get("/users").status_code == 403

    admin = app.test_client()
    google_sign_in(admin, google, "admin@ncit.edu.np")
    assert "alum@gmail.com" not in [u["email"] for u in admin.get("/users").json["items"]]
    assert [u["email"] for u in admin.get("/users?kind=external").json["items"]] == ["alum@gmail.com"]
    # the Super Admin can't grant a dashboard role to an outside address
    res = admin.post("/users/grants", json={"email": "alum@gmail.com", "role": "content_admin"}, headers=csrf(admin))
    assert res.status_code == 422


def test_dev_login_returns_the_code(app, client, mail):
    app.config["DEV_LOGIN"] = True
    res = client.post("/code/request", json={"email": "dev@gmail.com", "purpose": "applicant"})
    assert res.json["dev_code"] == last_code(mail)
