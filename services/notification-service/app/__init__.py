"""notification-service: sends the website's emails and keeps the Email log.

The worker (python -m app.worker) does the sending; this web app only serves
the Email log to Super Admins and lets them retry a failed email.
"""

import os

from flask import Flask, g, jsonify
from ncit_common import configure_logging, register_error_handlers
from ncit_common.revocation import RedisRevocationStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base
from .settings import config_from_env

SERVICE_NAME = "notification-service"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///notify-dev.db"),
        REDIS_URL=os.environ.get("REDIS_URL", ""),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        JWT_AUDIENCE="ncit-web",
        JWT_ISSUER="ncit-auth",
        MAIL_KEEP_SENSITIVE=os.environ.get("MAIL_KEEP_SENSITIVE", "false").lower() in ("1", "true", "yes"),
        **config_from_env(),
    )
    if config:
        app.config.update(config)
    if app.config["REDIS_URL"] and app.config.get("JWT_REVOCATION") is None:
        import redis

        app.config["JWT_REVOCATION"] = RedisRevocationStore(redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True))

    configure_logging(app, SERVICE_NAME)
    register_error_handlers(app)

    engine = create_engine(app.config["DATABASE_URL"], pool_pre_ping=True)
    if app.config["DATABASE_URL"].startswith("sqlite"):
        Base.metadata.create_all(engine)
    app.extensions["db"] = sessionmaker(bind=engine, expire_on_commit=False)

    @app.teardown_appcontext
    def _close(exc):
        session = g.pop("db", None)
        if session is not None:
            if exc is not None:
                session.rollback()
            session.close()

    from .routes.log import bp as log_bp
    from .routes.me import bp as me_bp

    app.register_blueprint(log_bp)
    app.register_blueprint(me_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME, smtp=bool(app.config["SMTP_HOST"]))

    return app
