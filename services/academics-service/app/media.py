"""Photo uploads for department pages (shared rules in ncit_common.media)."""

from flask import current_app
from ncit_common.media import save_image


def save_photo(upload, slug: str) -> str:
    return save_image(upload, media_root=current_app.config["MEDIA_ROOT"], service="academics", group=slug)
