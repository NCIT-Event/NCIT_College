"""Where the search service finds the other services (internal addresses, not through the gateway)."""

import os

DEFAULTS = {
    "academics": "http://academics-service:8000", "content": "http://content-service:8000",
    "events": "http://event-service:8000", "eca": "http://eca-service:8000",
    "careers": "http://career-service:8000", "admissions": "http://admission-service:8000",
}


def source_urls() -> dict:
    urls = {k: os.environ.get(f"{k.upper()}_URL", v) for k, v in DEFAULTS.items()}
    urls["pages"] = ""
    return urls
