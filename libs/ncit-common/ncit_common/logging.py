"""Structured JSON logs with a request id carried across services."""

import json
import logging
import sys
import uuid

from flask import Flask, g, request

REQUEST_ID_HEADER = "X-Request-ID"


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "level": record.levelname.lower(),
            "service": self.service,
            "message": record.getMessage(),
            "logger": record.name,
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            entry["request_id"] = request_id
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = g.get("request_id")
        except RuntimeError:  # outside a request context
            record.request_id = None
        return True


def configure_logging(app: Flask, service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    handler.addFilter(_RequestIdFilter())
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex

    @app.after_request
    def _echo_request_id(response):
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "")
        return response
