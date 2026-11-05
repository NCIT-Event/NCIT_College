"""Sign-in with an emailed one-time code, for people without a college account:
applicants (admissions and jobs) and alumni.

Mounted by the gateway at /api/v1/auth/code/ (rate limited there as well).

    POST /code/request {email, purpose}      -> emails a 6-digit code
    POST /code/verify  {email, code, name?}  -> signs in (same cookies as Google sign-in)

These accounts are "external": they get only the role they signed in for
(applicant or alumni), which opens the applicant and alumni portals and
nothing in the dashboard. College addresses must use Google sign-in.
"""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError
from sqlalchemy import func, select

from ..models import OneTimeCode, RoleGrant, User, utcnow
from ..roles import EXTERNAL_ROLES
from ..services import client_ip, db, domain, emit
from .auth import _set_session_cookies, _start_session, serialize_user

bp = Blueprint("code", __name__, url_prefix="/code")

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
MAX_CODES = 3  # per email per window
WINDOW = timedelta(minutes=15)
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")


def _hash(email: str, code: str) -> str:
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _email(value) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ApiError(422, "invalid_email", "Enter a valid email address.")
    if email.endswith("@" + domain()):
        raise ApiError(422, "use_google", f"@{domain()} accounts sign in with Google. Use the Google button.")
    return email


def _purpose(value) -> str:
    if value not in EXTERNAL_ROLES:
        raise ApiError(422, "invalid_purpose", "Choose what you are signing in for.")
    return value


@bp.post("/request")
def request_code():
    body = request.get_json(silent=True) or {}
    email, purpose = _email(body.get("email")), _purpose(body.get("purpose"))
    now = utcnow()
    recent = db().scalar(select(func.count(OneTimeCode.id)).where(
        OneTimeCode.email == email, OneTimeCode.created_at > now - WINDOW)) or 0
    if recent >= MAX_CODES:
        raise ApiError(429, "too_many_codes", "Too many codes requested. Wait 15 minutes, then try again.")
    user = db().scalar(select(User).where(User.email == email))
    if user is not None and user.status == "suspended":
        raise ApiError(403, "account_suspended", "This account is suspended. Contact the college.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    db().add(OneTimeCode(email=email, purpose=purpose, code_hash=_hash(email, code),
                         expires_at=now + CODE_TTL, ip=client_ip()))
    db().commit()
    current_app.config["MAIL"].send(email, "sign_in_code", {"code": code, "purpose": purpose, "minutes": 10},
                                    sensitive=True)
    out = {"ok": True, "sent_to": email, "expires_in": int(CODE_TTL.total_seconds())}
    if current_app.config["DEV_LOGIN"]:
        out["dev_code"] = code  # local development only: no mail server needed to try the portals
    return jsonify(out)


@bp.post("/verify")
def verify_code():
    body = request.get_json(silent=True) or {}
    email = _email(body.get("email"))
    code = re.sub(r"\D", "", str(body.get("code") or ""))
    now = utcnow()
    otp = db().scalar(select(OneTimeCode).where(OneTimeCode.email == email, OneTimeCode.used_at.is_(None))
                      .order_by(OneTimeCode.created_at.desc()))
    if otp is None or otp.expires_at <= now or otp.attempts >= MAX_ATTEMPTS:
        raise ApiError(422, "code_expired", "That code has expired. Request a new one.")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash(email, code)):
        db().commit()
        left = MAX_ATTEMPTS - otp.attempts
        emit("user.sign_in_refused", actor=None, entity_id=email,
             data={"reason": "wrong_code", "email": email, "method": "email_code"})
        if left <= 0:
            raise ApiError(422, "code_expired", "Too many wrong codes. Request a new one.")
        raise ApiError(422, "wrong_code", f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left.")
    otp.used_at = now

    user = db().scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, kind="external", status="active")
        db().add(user)
        db().flush()
    if user.status == "suspended":
        db().commit()
        raise ApiError(403, "account_suspended", "This account is suspended. Contact the college.")
    name = str(body.get("name") or "").strip()[:200]
    if name and not user.name:
        user.name = name
    user.status, user.last_login_at = "active", now
    if not any(g.role == otp.purpose for g in user.grants):
        user.grants.append(RoleGrant(user_id=user.id, role=otp.purpose, scope="*"))
    db().flush()
    access, refresh = _start_session(user)
    emit("user.signed_in", actor=user, entity_id=user.id, data={"method": "email_code", "purpose": otp.purpose})
    return _set_session_cookies(jsonify(user=serialize_user(user)), access, refresh)
