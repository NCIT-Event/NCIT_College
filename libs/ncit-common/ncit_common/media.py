"""Safe file uploads for content services (needs the `media` extra: Pillow).

Images are decoded and re-encoded as fresh JPEGs: anything that isn't really
an image is rejected, EXIF (including GPS location) is stripped, phone-camera
rotation is fixed and the size is capped. PDFs are checked for a PDF header
and stored under a random name. Public files are served by the gateway from
/media/. Private files (application documents, CVs) are saved with
private=True outside the public folder and returned only by the owning
service after a permission check (send_private).
"""

import re
import uuid
from io import BytesIO
from pathlib import Path

from .errors import ApiError

IMAGE_MAX_BYTES = 8 * 1024 * 1024
PDF_MAX_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600


PRIVATE_PREFIX = "private:"
PRIVATE_KEY_RE = re.compile(r"^private:([a-z]+)/([a-z0-9-]+)/([a-f0-9]{32}\.(?:jpg|pdf))$")


def _target(media_root: str, service: str, group: str, ext: str, private: bool = False) -> tuple[Path, str]:
    folder = Path(media_root) / service / group
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    if private:  # not under /media: only the owning service can hand it out, after a permission check
        return folder / name, f"{PRIVATE_PREFIX}{service}/{group}/{name}"
    return folder / name, f"/media/{service}/{group}/{name}"


def private_path(media_root: str, key: str) -> Path:
    """Resolve a private file key (from save_image/save_pdf with private=True) to its path, or raise 404."""
    m = PRIVATE_KEY_RE.match(key or "")
    if not m:
        raise ApiError(404, "file_not_found", "That file isn't available.")
    path = Path(media_root) / m.group(1) / m.group(2) / m.group(3)
    if not path.is_file():
        raise ApiError(404, "file_not_found", "That file isn't available.")
    return path


PUBLIC_URL_RE = re.compile(r"^/media/([a-z]+)/([a-z0-9-]+)/([a-f0-9]{32}\.(?:jpg|pdf))$")


def remove_file(media_root: str, key: str | None) -> bool:
    """Delete a file this module saved, given its private key or /media/ URL. Call it when an
    upload is replaced, so an old document, CV or photo doesn't stay on disk (or, for public
    photos, at its old address). Anything that isn't one of our own file names is ignored."""
    m = PRIVATE_KEY_RE.match(key or "") or PUBLIC_URL_RE.match(key or "")
    if not m:
        return False
    path = Path(media_root) / m.group(1) / m.group(2) / m.group(3)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def send_private(media_root: str, key: str, download_name: str):
    """Flask response for a private file. Call only after checking who may see it."""
    from flask import send_file

    path = private_path(media_root, key)
    mimetype = "application/pdf" if path.suffix == ".pdf" else "image/jpeg"
    resp = send_file(path, mimetype=mimetype, download_name=download_name, as_attachment=path.suffix == ".pdf",
                     max_age=0)
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def save_image(upload, *, media_root: str, service: str, group: str, max_side: int = MAX_SIDE,
               private: bool = False) -> str:
    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs
    data = upload.read(IMAGE_MAX_BYTES + 1)
    if len(data) > IMAGE_MAX_BYTES:
        raise ApiError(413, "file_too_large", "That photo is larger than 8 MB. Use a smaller one.")
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ApiError(422, "not_an_image", "That file isn't a photo we can use. Upload a JPEG, PNG or WebP image.") from exc
    if img.format not in ("JPEG", "PNG", "WEBP"):
        raise ApiError(422, "not_an_image", "Upload a JPEG, PNG or WebP image.")

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    path, url = _target(media_root, service, group, "jpg", private)
    img.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    return url


def save_pdf(upload, *, media_root: str, service: str, group: str, private: bool = False) -> str:
    data = upload.read(PDF_MAX_BYTES + 1)
    if len(data) > PDF_MAX_BYTES:
        raise ApiError(413, "file_too_large", "That PDF is larger than 10 MB. Compress it or split it.")
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ApiError(422, "not_a_pdf", "That file isn't a PDF. Save the document as PDF and upload it again.")
    path, url = _target(media_root, service, group, "pdf", private)
    path.write_bytes(data)
    return url
