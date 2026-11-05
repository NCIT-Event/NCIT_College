"""auth-service: Google sign-in for @ncit.edu.np, JWT sessions, roles and access."""

import logging
import os

import click
from cryptography.hazmat.primitives import serialization
from flask import Flask, g, jsonify
from ncit_common import (
    MemoryEventPublisher,
    MemoryRevocationStore,
    configure_logging,
    register_error_handlers,
)
from ncit_common.events import EventPublisher
from ncit_common.mail import MailQueue, MemoryMailQueue
from ncit_common.revocation import RedisRevocationStore
from ncit_common.shared import init_shared
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .google import GoogleClient
from .models import Base

SERVICE_NAME = "auth-service"


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def _public_from_private(private_pem: str) -> str:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    private_key = os.environ.get("JWT_PRIVATE_KEY", "").replace("\\n", "\n")
    app.config.update(
        SERVICE_NAME=SERVICE_NAME,
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///auth-dev.db"),
        REDIS_URL=os.environ.get("REDIS_URL", ""),
        JWT_PRIVATE_KEY=private_key,
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        JWT_KID=os.environ.get("JWT_KID", "ncit-1"),
        JWT_ISSUER="ncit-auth",
        JWT_AUDIENCE="ncit-web",
        GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID", ""),
        GOOGLE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        OAUTH_REDIRECT_URI=os.environ.get("OAUTH_REDIRECT_URI", ""),
        ALLOWED_DOMAIN=os.environ.get("ALLOWED_DOMAIN", "ncit.edu.np").lower(),
        SUPER_ADMIN_EMAILS={e.strip().lower() for e in os.environ.get("SUPER_ADMIN_EMAILS", "").split(",") if e.strip()},
        DEFAULT_ROLE=os.environ.get("DEFAULT_ROLE", "student"),
        # "computer=amit@ncit.edu.np, civil=someone@ncit.edu.np": HOD roles granted by `flask bootstrap`
        HOD_ASSIGNMENTS=os.environ.get("HOD_ASSIGNMENTS", ""),
        COOKIE_SECURE=_env_bool("COOKIE_SECURE", True),
        DEV_LOGIN=_env_bool("DEV_LOGIN", False),
        AUTH_COOKIE_PATH="/api/v1/auth",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # CSV imports and JSON bodies
    )
    # Flask's signed session cookie only carries OAuth state/nonce/PKCE for the
    # few minutes between /google/login and /google/callback.
    app.config.update(
        SESSION_COOKIE_NAME="ncit_oauth",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=600,
    )
    if config:
        app.config.update(config)
    app.config["SESSION_COOKIE_SECURE"] = app.config["COOKIE_SECURE"]
    app.config["SESSION_COOKIE_PATH"] = app.config["AUTH_COOKIE_PATH"]

    if app.config["JWT_PRIVATE_KEY"] and not app.config["JWT_PUBLIC_KEY"]:
        app.config["JWT_PUBLIC_KEY"] = _public_from_private(app.config["JWT_PRIVATE_KEY"])
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is required (see .env.example)")
    if app.config["DEV_LOGIN"] and app.config["COOKIE_SECURE"]:
        raise RuntimeError("DEV_LOGIN is for local development only and cannot run with COOKIE_SECURE=true")

    configure_logging(app, SERVICE_NAME)
    register_error_handlers(app)
    if app.config["DEV_LOGIN"]:
        app.logger.warning("DEV_LOGIN is ON: anyone can sign in as any @%s address. Never enable this in production.",
                           app.config["ALLOWED_DOMAIN"])

    # Database
    engine = create_engine(app.config["DATABASE_URL"], pool_pre_ping=True, future=True)
    if app.config["DATABASE_URL"].startswith("sqlite"):
        Base.metadata.create_all(engine)  # dev and tests; Postgres uses Alembic migrations
    app.extensions["db"] = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    @app.teardown_appcontext
    def _close_session(exc):
        session = g.pop("db", None)
        if session is not None:
            if exc is not None:
                session.rollback()
            session.close()

    # Revocation store and event stream: Redis in production, memory otherwise
    client = None
    if app.config["REDIS_URL"]:
        import redis
        client = redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    if app.config.get("JWT_REVOCATION") is None:
        app.config["JWT_REVOCATION"] = RedisRevocationStore(client) if client else MemoryRevocationStore()
    if app.config.get("EVENTS") is None:
        app.config["EVENTS"] = EventPublisher(client, SERVICE_NAME) if client else MemoryEventPublisher(SERVICE_NAME)
    if app.config.get("MAIL") is None:
        app.config["MAIL"] = MailQueue(client, SERVICE_NAME) if client else MemoryMailQueue(SERVICE_NAME)
    init_shared(app, client, SERVICE_NAME)  # Redis public-page cache + in-app notifications

    app.extensions["google"] = app.config.get("GOOGLE_CLIENT") or GoogleClient(
        app.config["GOOGLE_CLIENT_ID"], app.config["GOOGLE_CLIENT_SECRET"],
        app.config["OAUTH_REDIRECT_URI"], app.config["ALLOWED_DOMAIN"],
    )

    from .routes.auth import bp as auth_bp
    from .routes.code import bp as code_bp
    from .routes.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(code_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME)

    @app.get("/ready")
    def ready():
        problems = []
        if not app.config["JWT_PRIVATE_KEY"]:
            problems.append("JWT_PRIVATE_KEY")
        if not app.extensions["google"].configured and not app.config["DEV_LOGIN"]:
            problems.append("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/OAUTH_REDIRECT_URI")
        if problems:
            return jsonify(status="not_ready", missing=problems), 503
        return jsonify(status="ready", service=SERVICE_NAME)

    @app.cli.command("grant-super-admin")
    @click.argument("email")
    def grant_super_admin(email):
        """Give EMAIL the Super Admin role (creates an invited user if needed)."""
        from .services import grant_role

        with app.app_context():
            session = app.extensions["db"]()
            user, _ = grant_role(session, email=email, role="super_admin", scope=None, expires_at=None, actor=None)
            session.commit()
            click.echo(f"Super Admin granted to {user.email} (status: {user.status})")

    @app.cli.command("bootstrap")
    def bootstrap():
        """Grant HOD roles from HOD_ASSIGNMENTS; with DEV_LOGIN also create demo HOD and admin accounts.

        Safe to run on every start: existing grants are kept, nothing is removed.
        """
        from .roles import DEMO_ADMINS, DEPARTMENTS
        from .services import grant_role

        session = app.extensions["db"]()
        assignments = []
        for pair in filter(None, (x.strip() for x in app.config["HOD_ASSIGNMENTS"].replace(";", ",").split(","))):
            dept, _, email = pair.partition("=")
            if dept.strip() not in DEPARTMENTS or not email.strip():
                raise click.ClickException(f"HOD_ASSIGNMENTS: can't read '{pair}'. Use department=email, "
                                           f"with departments from: {', '.join(DEPARTMENTS)}")
            assignments.append((dept.strip(), email.strip().lower()))
        if app.config["DEV_LOGIN"]:
            domain = app.config["ALLOWED_DOMAIN"]
            assignments += [(dept, f"hod.{dept}@{domain}") for dept in DEPARTMENTS
                            if not any(d == dept and e == f"hod.{dept}@{domain}" for d, e in assignments)]
        for dept, email in assignments:
            grant_role(session, email=email, role="hod", scope=dept, expires_at=None, actor=None)
            click.echo(f"HOD of {DEPARTMENTS[dept]}: {email}")
        if app.config["DEV_LOGIN"]:
            domain = app.config["ALLOWED_DOMAIN"]
            for role, local in DEMO_ADMINS.items():
                email = f"{local}@{domain}"
                grant_role(session, email=email, role=role, scope=None, expires_at=None, actor=None)
                click.echo(f"Demo {role}: {email}")
        session.commit()
        if not assignments:
            click.echo("No HOD assignments (set HOD_ASSIGNMENTS to pre-assign Heads of Department).")

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return app
