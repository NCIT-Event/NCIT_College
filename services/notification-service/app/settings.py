"""Mail settings from the environment (shared by the web app and the worker)."""

import os


def config_from_env() -> dict:
    return {
        "SMTP_HOST": os.environ.get("SMTP_HOST", ""), "SMTP_PORT": os.environ.get("SMTP_PORT", "587"),
        "SMTP_USER": os.environ.get("SMTP_USER", ""), "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
        "SMTP_STARTTLS": os.environ.get("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes"),
        "MAIL_FROM": os.environ.get("MAIL_FROM", "NCIT <no-reply@ncit.edu.np>"),
    }
