"""Editable-field validation shared by content services.

Each service declares what editors may change as a dict of `Field`s; `apply`
validates a JSON body against it and sets the values on a model, returning
readable messages ("Title can't be empty.") on mistakes.
"""

import re
from datetime import UTC, datetime, timedelta, timezone

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
STATIC_PHOTO_RE = re.compile(r"^/assets/img/photos/[A-Za-z0-9._-]+\.(jpg|png|webp)$")
NEPAL = timezone(timedelta(hours=5, minutes=45))


class Field:
    """One editable field.

    kind: str | text | int | num | bool | email | url | datetime |
          media (an uploaded image; `media_root` names the service folder) |
          file  (an uploaded document, e.g. a PDF)
    """

    def __init__(self, label: str, kind: str = "str", max_len: int = 200, required: bool = False,
                 choices: tuple | None = None, lo: float | None = None, hi: float | None = None,
                 media_root: str = ""):
        self.label, self.kind, self.max_len, self.required = label, kind, max_len, required
        self.choices, self.lo, self.hi, self.media_root = choices, lo, hi, media_root

    def _media_ok(self, text: str, extensions: str) -> bool:
        if not text:
            return True
        pattern = rf"^/media/{re.escape(self.media_root)}/[a-z0-9-]+/[a-f0-9]{{32}}\.({extensions})$"
        return bool(re.match(pattern, text)) or (self.kind == "media" and bool(STATIC_PHOTO_RE.match(text)))

    def clean(self, value):
        if self.kind == "bool":
            return bool(value)
        if self.kind in ("int", "num"):
            try:
                number = int(value) if self.kind == "int" else round(float(value), 1)
            except (TypeError, ValueError) as exc:
                raise ApiError(422, "invalid_field", f"{self.label} must be a number.") from exc
            if (self.lo is not None and number < self.lo) or (self.hi is not None and number > self.hi):
                raise ApiError(422, "invalid_field", f"{self.label} must be between {self.lo:g} and {self.hi:g}.")
            return number
        if self.kind == "datetime":
            return self._clean_datetime(value)
        text = "" if value is None else str(value).strip()
        text = text.replace("\r\n", "\n")
        if self.required and not text:
            raise ApiError(422, "invalid_field", f"{self.label} can't be empty.")
        if len(text) > self.max_len:
            raise ApiError(422, "invalid_field", f"{self.label} is too long ({len(text)} of {self.max_len} characters).")
        if self.choices and text not in self.choices:
            raise ApiError(422, "invalid_field", f"Choose a valid {self.label.lower()}.")
        if self.kind == "email" and text and not EMAIL_RE.match(text):
            raise ApiError(422, "invalid_field", f"{self.label} doesn't look like an email address.")
        if self.kind == "media" and not self._media_ok(text, "jpg"):
            raise ApiError(422, "invalid_field", f"Upload the {self.label.lower()} with the photo button.")
        if self.kind == "file" and not self._media_ok(text, "pdf"):
            raise ApiError(422, "invalid_field", f"Upload the {self.label.lower()} with the file button.")
        if self.kind == "url" and text and not text.startswith(("https://", "/")):
            raise ApiError(422, "invalid_field", f"{self.label} must start with https:// or /")
        return text

    def _clean_datetime(self, value):
        if value in (None, ""):
            if self.required:
                raise ApiError(422, "invalid_field", f"{self.label} can't be empty.")
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).strip())  # Python 3.11+ accepts a trailing Z
            except ValueError as exc:
                raise ApiError(422, "invalid_field", f"{self.label} isn't a valid date and time.") from exc
        if dt.tzinfo is None:  # a bare local time from a form means Nepal time
            dt = dt.replace(tzinfo=NEPAL)
        return dt.astimezone(UTC)


def apply(obj, spec: dict, data: dict, *, partial: bool, allowed: set | None = None) -> list[str]:
    """Validate `data` against `spec` and set it on `obj`. Returns the changed field names."""
    unknown = set(data) - set(spec)
    if unknown:
        raise ApiError(422, "unknown_field", f"These fields can't be edited: {', '.join(sorted(unknown))}.")
    changed = []
    for name, field in spec.items():
        if name not in data:
            if not partial and field.required:
                raise ApiError(422, "invalid_field", f"{field.label} can't be empty.")
            continue
        if allowed is not None and name not in allowed:
            raise ApiError(403, "forbidden_field", f"Only a Super Admin can change the {field.label.lower()}.")
        value = field.clean(data[name])
        current = getattr(obj, name, None)
        if isinstance(current, datetime) and current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        if current != value:
            setattr(obj, name, value)
            changed.append(name)
    return changed
