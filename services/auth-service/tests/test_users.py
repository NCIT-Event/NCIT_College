import pytest
from conftest import csrf, google_sign_in


@pytest.fixture
def admin(client, google):
    google_sign_in(client, google, "admin@ncit.edu.np", name="Admin")
    return client


def grant(client, **body):
    return client.post("/users/grants", json=body, headers=csrf(client))


def test_non_admin_cannot_list_users(client, google):
    google_sign_in(client, google, "student@ncit.edu.np")
    assert client.get("/users").status_code == 403


def test_grant_to_new_email_creates_invite(admin, events):
    res = grant(admin, email="new.teacher@ncit.edu.np", role="teacher")
    assert res.status_code == 201 and res.json["invited"] is True
    assert res.json["user"]["status"] == "invited"
    assert events.events[-1]["type"] == "role.granted"
    users = admin.get("/users?q=new.teacher").json
    assert users["total"] == 1


def test_grant_rejects_outside_email(admin):
    res = grant(admin, email="someone@gmail.com", role="teacher")
    assert res.status_code == 422 and res.json["error"]["code"] == "wrong_domain"


def test_hod_needs_a_department(admin):
    assert grant(admin, email="hod@ncit.edu.np", role="hod").status_code == 422
    res = grant(admin, email="hod@ncit.edu.np", role="hod", scope="computer")
    assert res.json["user"]["roles"][0]["scope"] == "dept:computer"
    assert res.json["user"]["roles"][0]["scope_label"] == "Computer Engineering"


def test_grant_requires_csrf(admin):
    assert admin.post("/users/grants", json={"email": "x@ncit.edu.np", "role": "teacher"}).status_code == 403


def test_invited_user_gets_granted_role_on_first_sign_in(app, admin, google):
    grant(admin, email="hod@ncit.edu.np", role="hod", scope="civil")
    other = app.test_client()
    google_sign_in(other, google, "hod@ncit.edu.np")
    roles = [r["role"] for r in other.get("/me").json["user"]["roles"]]
    assert roles == ["hod"]  # no default student role on top


def test_revoked_role_stops_working_immediately(app, admin, google):
    """Phase 1 gate: a revoked role loses access without waiting for token expiry."""
    grant(admin, email="event@ncit.edu.np", role="event_admin")
    member = app.test_client()
    google_sign_in(member, google, "event@ncit.edu.np")
    old_token = member.get_cookie("ncit_access").value

    user_id = member.get("/me").json["user"]["id"]
    grant_id = admin.get("/users?q=event@").json["items"][0]["roles"][0]["id"]
    res = admin.delete(f"/users/{user_id}/grants/{grant_id}", headers=csrf(admin))
    assert res.status_code == 200

    assert member.get("/me", headers={"Authorization": f"Bearer {old_token}"}).json["error"]["code"] == "token_revoked"
    # The dashboard refreshes and continues with the reduced role set.
    assert member.post("/refresh", headers=csrf(member)).status_code == 200
    assert member.get("/me").json["user"]["roles"] == []


def test_cannot_remove_last_super_admin(admin):
    me = admin.get("/me").json["user"]
    res = admin.delete(f"/users/{me['id']}/grants/{me['roles'][0]['id']}", headers=csrf(admin))
    assert res.status_code == 409 and res.json["error"]["code"] == "last_super_admin"


def test_suspend_ends_sessions(app, admin, google):
    member = app.test_client()
    google_sign_in(member, google, "teacher@ncit.edu.np")
    user_id = member.get("/me").json["user"]["id"]
    assert admin.post(f"/users/{user_id}/suspend", headers=csrf(admin)).status_code == 200
    assert member.get("/me").status_code == 401
    assert member.post("/refresh", headers=csrf(member)).status_code == 401
    # and they cannot sign in again
    again = app.test_client()
    assert google_sign_in(again, google, "teacher@ncit.edu.np").headers["Location"].endswith("error=account_suspended")
    assert admin.post(f"/users/{user_id}/reactivate", headers=csrf(admin)).json["user"]["status"] == "active"


def test_cannot_suspend_self(admin):
    me = admin.get("/me").json["user"]
    assert admin.post(f"/users/{me['id']}/suspend", headers=csrf(admin)).status_code == 409


def test_csv_import_reports_each_row(admin):
    body = ("email,role,department,expires\n"
            "a@ncit.edu.np,Teacher,,\n"
            "b@ncit.edu.np,hod,computer,2099-01-31\n"
            "c@gmail.com,teacher,,\n"
            "d@ncit.edu.np,hod,,\n")
    res = admin.post("/users/import", data=body, content_type="text/csv", headers=csrf(admin)).json
    assert res["granted"] == 2 and res["failed"] == 2
    assert [r["ok"] for r in res["results"]] == [True, True, False, False]


def test_summary_counts_invites(admin):
    grant(admin, email="x@ncit.edu.np", role="teacher")
    assert admin.get("/users/summary").json["invited"] == 1


def test_roles_catalogue(admin):
    data = admin.get("/roles").json
    assert {"code": "computer", "name": "Computer Engineering"} in data["departments"]
    assert any(r["code"] == "hod" and r["scoped"] == "dept" for r in data["roles"])


def test_bootstrap_assigns_hods(app):
    app.config["HOD_ASSIGNMENTS"] = "computer=Amit.S@ncit.edu.np; civil=civil.head@ncit.edu.np"
    result = app.test_cli_runner().invoke(args=["bootstrap"])
    assert result.exit_code == 0, result.output
    assert "HOD of Computer Engineering: amit.s@ncit.edu.np" in result.output
    assert "hod.it@" not in result.output  # demo accounts only with DEV_LOGIN
    again = app.test_cli_runner().invoke(args=["bootstrap"])  # idempotent
    assert again.exit_code == 0


def test_bootstrap_rejects_unknown_department(app):
    app.config["HOD_ASSIGNMENTS"] = "physics=x@ncit.edu.np"
    result = app.test_cli_runner().invoke(args=["bootstrap"])
    assert result.exit_code != 0 and "physics" in result.output


def test_bootstrap_demo_hods_with_dev_login(app, client, google):
    app.config["DEV_LOGIN"] = True
    result = app.test_cli_runner().invoke(args=["bootstrap"])
    assert "hod.civil@ncit.edu.np" in result.output and "hod.management@ncit.edu.np" in result.output
    res = client.post("/dev/login", json={"email": "hod.civil@ncit.edu.np"})
    assert res.status_code == 200
    roles = client.get("/me").json["user"]["roles"]
    assert [(r["role"], r["scope"]) for r in roles] == [("hod", "dept:civil")]


def test_role_changes_are_notified(admin, app):
    sent = app.config["NOTIFY"].sent
    grant(admin, email="new.admin@ncit.edu.np", role="event_admin")
    assert sent[-1]["to"] == "new.admin@ncit.edu.np" and "Event Admin" in sent[-1]["title"] and sent[-1]["kind"] == "success"
    user = admin.get("/users?q=new.admin").json["items"][0]
    admin.delete(f"/users/{user['id']}/grants/{user['roles'][0]['id']}", headers=csrf(admin))
    assert "removed" in sent[-1]["title"]


def test_access_token_ends_when_a_role_expires(app):
    """Authorization review: a role with an expiry date stops working at that moment, not up to 15 minutes later."""
    from datetime import timedelta

    import jwt
    from app.models import RoleGrant, User, utcnow
    from app.tokens import ACCESS_TTL, issue_access_token

    with app.app_context():
        s = app.extensions["db"]()
        u = User(email="temp@ncit.edu.np", name="Temp", status="active")
        s.add(u)
        s.flush()
        soon = utcnow() + timedelta(minutes=3)
        u.grants.append(RoleGrant(user_id=u.id, role="event_admin", scope="*", expires_at=soon))
        s.commit()
        token, claims = issue_access_token(u)
        assert abs(claims["exp"] - soon.timestamp()) < 2
        u.grants[0].expires_at = None
        s.commit()
        _, claims = issue_access_token(u)
        assert claims["exp"] - claims["iat"] > ACCESS_TTL - 2
        assert jwt.decode(token, options={"verify_signature": False})["roles"][0]["role"] == "event_admin"
