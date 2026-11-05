"""Create .env at the repo root with fresh secrets (run once per environment).

    python3 infra/setup_env.py            # writes .env (refuses to overwrite)
    python3 infra/setup_env.py --force    # replaces it: everyone is signed out
    python3 infra/setup_env.py --output staging.env   # writes another file (e.g. for a staging server)

Needs the `cryptography` package (pip install cryptography).
"""

import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parent.parent
TARGET = Path(sys.argv[sys.argv.index("--output") + 1]).resolve() if "--output" in sys.argv else ROOT / ".env"


def one_line(pem: bytes) -> str:
    return pem.decode().strip().replace("\n", "\\n")


def main():
    if TARGET.exists() and "--force" not in sys.argv:
        sys.exit(f"{TARGET} already exists. Use --force to replace it (this signs everyone out).")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    template = (ROOT / ".env.example").read_text()
    values = {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "JWT_PRIVATE_KEY": f'"{one_line(private)}"',
        "JWT_PUBLIC_KEY": f'"{one_line(public)}"',
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "AUTH_DB_PASSWORD": secrets.token_urlsafe(24),
        "AUDIT_DB_PASSWORD": secrets.token_urlsafe(24),
        "ACADEMICS_DB_PASSWORD": secrets.token_urlsafe(24),
        "CONTENT_DB_PASSWORD": secrets.token_urlsafe(24),
        "EVENTS_DB_PASSWORD": secrets.token_urlsafe(24),
        "ECA_DB_PASSWORD": secrets.token_urlsafe(24),
        "NOTIFY_DB_PASSWORD": secrets.token_urlsafe(24),
        "ADMISSIONS_DB_PASSWORD": secrets.token_urlsafe(24),
        "CAREERS_DB_PASSWORD": secrets.token_urlsafe(24),
        "ALUMNI_DB_PASSWORD": secrets.token_urlsafe(24),
        "SEARCH_DB_PASSWORD": secrets.token_urlsafe(24),
    }
    lines = []
    for line in template.splitlines():
        name = line.split("=", 1)[0]
        lines.append(f"{name}={values[name]}" if name in values and "=" in line else line)
    TARGET.write_text("\n".join(lines) + "\n")
    TARGET.chmod(0o600)
    print(f"Wrote {TARGET}. Next: fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and SUPER_ADMIN_EMAILS.")


if __name__ == "__main__":
    main()
