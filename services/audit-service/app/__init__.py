"""audit-service: who changed what, and when. Super Admin only."""

import os

from flask import Flask, g, jsonify, request
from ncit_common import configure_logging, register_error_handlers, require_role
from ncit_common.revocation import RedisRevocationStore
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import sessionmaker

from .models import AuditEntry, Base

SERVICE_NAME = "audit-service"
MAX_PER_PAGE = 100


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///audit-dev.db"),
        REDIS_URL=os.environ.get("REDIS_URL", ""),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        JWT_AUDIENCE="ncit-web",
        JWT_ISSUER="ncit-auth",
    )
    if config:
        app.config.update(config)
    if app.config.get("JWT_REVOCATION") is None and app.config["REDIS_URL"]:
        import redis
        app.config["JWT_REVOCATION"] = RedisRevocationStore(
            redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True))

    configure_logging(app, SERVICE_NAME)
    register_error_handlers(app)

    engine = create_engine(app.config["DATABASE_URL"], pool_pre_ping=True)
    if app.config["DATABASE_URL"].startswith("sqlite"):
        Base.metadata.create_all(engine)
    app.extensions["db"] = sessionmaker(bind=engine, expire_on_commit=False)

    def db():
        if "db" not in g:
            g.db = app.extensions["db"]()
        return g.db

    @app.teardown_appcontext
    def _close(exc):
        s = g.pop("db", None)
        if s is not None:
            s.close()

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME)

    @app.get("/")
    @require_role("super_admin")
    def list_entries():
        q = (request.args.get("q") or "").strip().lower()
        event_type = request.args.get("type") or ""
        page = max(int(request.args.get("page", 1) or 1), 1)
        per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), MAX_PER_PAGE)
        stmt = select(AuditEntry)
        if event_type:
            stmt = stmt.where(AuditEntry.type.like(f"{event_type}%"))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(func.lower(AuditEntry.actor_email).like(like),
                                  func.lower(AuditEntry.entity_id).like(like),
                                  func.lower(AuditEntry.type).like(like)))
        total = db().scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db().scalars(stmt.order_by(AuditEntry.at.desc()).offset((page - 1) * per_page).limit(per_page)).all()
        return jsonify(total=total, page=page, per_page=per_page, items=[{
            "id": e.id, "type": e.type, "service": e.service, "at": e.at.isoformat(),
            "actor": {"id": e.actor_id, "email": e.actor_email},
            "entity": e.entity, "entity_id": e.entity_id, "data": e.data, "ip": e.ip,
        } for e in rows])

    return app
