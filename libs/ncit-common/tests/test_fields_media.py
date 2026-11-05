import io
from datetime import UTC, datetime

import pytest
from ncit_common import ApiError
from ncit_common.fields import Field, apply
from ncit_common.media import remove_file, save_image, save_pdf
from PIL import Image


class Obj:
    title = ""
    starts = None
    photo = ""


def test_apply_validates_and_reports_changes():
    spec = {"title": Field("Title", required=True, max_len=10), "photo": Field("Photo", "media", media_root="content")}
    o = Obj()
    assert apply(o, spec, {"title": "Hello"}, partial=True) == ["title"]
    with pytest.raises(ApiError) as e:
        apply(o, spec, {"title": ""}, partial=True)
    assert "can't be empty" in e.value.message
    with pytest.raises(ApiError):
        apply(o, spec, {"photo": "https://evil.example/x.jpg"}, partial=True)
    apply(o, spec, {"photo": "/media/content/banners/" + "a" * 32 + ".jpg"}, partial=True)
    with pytest.raises(ApiError) as e:
        apply(o, spec, {"nope": 1}, partial=True)
    assert e.value.code == "unknown_field"


def test_datetime_field_treats_bare_times_as_nepal_time():
    f = Field("Starts", "datetime")
    assert f.clean("2026-11-05T10:00") == datetime(2026, 11, 5, 4, 15, tzinfo=UTC)
    assert f.clean("2026-11-05T04:15:00Z") == datetime(2026, 11, 5, 4, 15, tzinfo=UTC)
    assert f.clean("") is None
    with pytest.raises(ApiError):
        f.clean("next tuesday")


def test_save_image_reencodes(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (3000, 1000), "blue").save(buf, "PNG")
    buf.seek(0)
    url = save_image(buf, media_root=str(tmp_path), service="content", group="banners")
    saved = Image.open(tmp_path / url.removeprefix("/media/"))
    assert saved.format == "JPEG" and saved.size == (1600, 533)


def test_save_pdf_checks_header(tmp_path):
    good = io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n")
    assert save_pdf(good, media_root=str(tmp_path), service="content", group="notices").endswith(".pdf")
    with pytest.raises(ApiError) as e:
        save_pdf(io.BytesIO(b"MZ\x90 not a pdf"), media_root=str(tmp_path), service="content", group="notices")
    assert e.value.code == "not_a_pdf"


def test_private_files_are_not_public(tmp_path):
    import pytest
    from flask import Flask
    from ncit_common.errors import ApiError
    from ncit_common.media import private_path, save_pdf, send_private

    class Upload:
        def __init__(self, data):
            self.data = data

        def read(self, n=-1):
            return self.data

    key = save_pdf(Upload(b"%PDF-1.4\n%%EOF\n"), media_root=str(tmp_path), service="admissions",
                   group="documents", private=True)
    assert key.startswith("private:admissions/documents/") and not key.startswith("/media")
    assert private_path(str(tmp_path), key).read_bytes().startswith(b"%PDF")
    for bad in ("private:admissions/../../etc/passwd", "/media/x.pdf", "private:admissions/documents/zz.pdf"):
        with pytest.raises(ApiError):
            private_path(str(tmp_path), bad)
    with Flask(__name__).test_request_context():
        resp = send_private(str(tmp_path), key, "transcript.pdf")
        assert resp.headers["Cache-Control"] == "private, no-store" and resp.mimetype == "application/pdf"


def test_mail_queue_memory():
    from ncit_common.mail import MemoryMailQueue

    q = MemoryMailQueue("x")
    q.send("a@b.com", "otp", {"code": "123456"}, sensitive=True)
    assert q.messages[0]["template"] == "otp" and q.messages[0]["sensitive"] is True


def test_remove_file_deletes_only_our_own_files(tmp_path):
    pdf = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
    key = save_pdf(pdf, media_root=str(tmp_path), service="admissions", group="documents", private=True)
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "PNG")
    buf.seek(0)
    url = save_image(buf, media_root=str(tmp_path), service="alumni", group="photos")
    (tmp_path / "secret.txt").write_text("keep me")
    assert remove_file(str(tmp_path), key) and remove_file(str(tmp_path), url)
    assert not list(tmp_path.rglob("*.pdf")) and not list(tmp_path.rglob("*.jpg"))
    assert remove_file(str(tmp_path), key) is False  # already gone
    for junk in ("", None, "/media/../secret.txt", "private:../../secret.txt", "/etc/passwd", "https://x/y.jpg"):
        assert remove_file(str(tmp_path), junk) is False
    assert (tmp_path / "secret.txt").read_text() == "keep me"
