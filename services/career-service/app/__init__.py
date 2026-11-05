"""career-service: job vacancies and job applications."""

import os

import click
from flask import Flask, g, jsonify
from ncit_common import MemoryEventPublisher, configure_logging, register_error_handlers
from ncit_common.events import EventPublisher
from ncit_common.mail import MailQueue, MemoryMailQueue
from ncit_common.revocation import RedisRevocationStore
from ncit_common.shared import init_shared
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

SERVICE_NAME = "career-service"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///careers-dev.db"),
        REDIS_URL=os.environ.get("REDIS_URL", ""),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        JWT_AUDIENCE="ncit-web",
        JWT_ISSUER="ncit-auth",
        MEDIA_ROOT=os.environ.get("MEDIA_ROOT", "media"),
        # documents only the owner and the officer may see; never under the public /media folder
        PRIVATE_MEDIA_ROOT=os.environ.get("PRIVATE_MEDIA_ROOT", "private-media"),
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,  # PDFs up to 10 MB
    )
    if config:
        app.config.update(config)

    client = None
    if app.config["REDIS_URL"]:
        import redis
        client = redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    if app.config.get("JWT_REVOCATION") is None and client is not None:
        app.config["JWT_REVOCATION"] = RedisRevocationStore(client)
    if app.config.get("EVENTS") is None:
        app.config["EVENTS"] = EventPublisher(client, SERVICE_NAME) if client else MemoryEventPublisher(SERVICE_NAME)
    if app.config.get("MAIL") is None:
        app.config["MAIL"] = MailQueue(client, SERVICE_NAME) if client else MemoryMailQueue(SERVICE_NAME)
    init_shared(app, client, SERVICE_NAME)  # Redis public-page cache + in-app notifications

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

    from .routes.editor import bp as editor_bp
    from .routes.me import bp as me_bp
    from .routes.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(editor_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME)

    @app.cli.command("seed")
    def seed_command():
        """Add sample vacancies if there are none yet (safe to run again)."""
        from .seed import seed

        created = seed(app.extensions["db"]())
        click.echo(f"Seeded: {', '.join(created) or 'nothing (vacancies already exist)'}")

    return app
