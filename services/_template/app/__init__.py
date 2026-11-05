"""Service template: copy this folder to start a new NCIT microservice.

Rename SERVICE_NAME, add Blueprints under app/, give the service its own
database, then add one route to gateway/nginx.conf. Nothing else changes.
"""

import os

from flask import Flask, jsonify
from ncit_common import configure_logging, register_error_handlers

SERVICE_NAME = os.environ.get("SERVICE_NAME", "template-service")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SERVICE_NAME=SERVICE_NAME,
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", ""),
        JWT_AUDIENCE="ncit-web",
        JWT_ISSUER="ncit-auth",
    )
    if config:
        app.config.update(config)

    configure_logging(app, SERVICE_NAME)
    register_error_handlers(app)

    @app.get("/health")
    def health():
        """Liveness: the process is up."""
        return jsonify(status="ok", service=SERVICE_NAME)

    @app.get("/ready")
    def ready():
        """Readiness: dependencies are configured. Real services also ping their DB."""
        missing = [k for k in ("DATABASE_URL",) if not app.config.get(k)]
        if missing:
            return jsonify(status="not_ready", missing=missing), 503
        return jsonify(status="ready", service=SERVICE_NAME)

    return app
