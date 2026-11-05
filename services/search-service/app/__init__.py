"""search-service: site search across every service's public content, and the sitemap.

The worker (python -m app.worker) keeps the index up to date; this web app
answers searches, serves /sitemap.xml and lets a Super Admin rebuild the index.
"""

import os

from flask import Flask, g, jsonify
from ncit_common import configure_logging, register_error_handlers
from ncit_common.revocation import RedisRevocationStore
from ncit_common.shared import init_shared
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .indexer import http_fetcher
from .models import Base
from .settings import source_urls

SERVICE_NAME = "search-service"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///search-dev.db"),
        REDIS_URL=os.environ.get("REDIS_URL", ""),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        JWT_AUDIENCE="ncit-web",
        JWT_ISSUER="ncit-auth",
        SITE_URL=os.environ.get("SITE_URL", "https://ncit.edu.np"),
    )
    if config:
        app.config.update(config)
    app.config.setdefault("FETCH", http_fetcher(source_urls()))
    client = None
    if app.config["REDIS_URL"]:
        import redis

        client = redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    if client is not None and app.config.get("JWT_REVOCATION") is None:
        app.config["JWT_REVOCATION"] = RedisRevocationStore(client)
    init_shared(app, client, SERVICE_NAME)  # Redis cache for search results and the sitemap

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

    from .routes.admin import bp as admin_bp
    from .routes.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME)

    return app
