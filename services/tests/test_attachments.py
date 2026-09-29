import io
import json
import os

import pytest
from fastapi import HTTPException
from google.adk.models import LlmRequest
from PIL import Image

# The agent reads its template at import. Nothing here calls Model Armor
os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from classify import attachments
from expenser.files import turn
from expenser.screen import free_text
from integrations.workspace import delegation, drive, gmail
from requisition import Requisition

REQUISITION = Requisition(
    response_number=482,
    response_id="r",
    submitted_by="ltanga@lekkacredit.com",
    submitted_at="2026-09-28T21:34:33Z",
    payable_to="LMS support",
    amount=60,
    comment="for September",
    files={"signed_requisition_form": ["A1"], "receipts": ["B2"]},
)


def file(field="receipts", mime_type="application/pdf", size=10, id="B2"):
    return {"field": field, "id": id, "mimeType": mime_type, "size": size, "data": b"x" * size}


@pytest.mark.parametrize("mime_type", sorted(drive.SHOWN))
def test_shown(mime_type):
    attachments.check([file(mime_type=mime_type)])


@pytest.mark.parametrize(
    "mime_type",
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "image/gif", "text/plain"],
)
def test_not_shown(mime_type):
    with pytest.raises(HTTPException) as e:
        attachments.check([file(mime_type=mime_type)])
    assert e.value.status_code == 422
    assert "receipts B2" in e.value.detail


def test_too_large():
    half = drive.MAX_BYTES // 2 + 1
    with pytest.raises(HTTPException) as e:
        attachments.check([file(size=half), file(size=half)])
    assert e.value.status_code == 422


def test_turn():
    content = turn(REQUISITION, [file("signed_requisition_form"), file(mime_type="image/png")])
    assert content.parts[0].text.startswith('{"response_number": 482')
    assert content.parts[1].text == "signed_requisition_form"
    assert content.parts[2].inline_data.mime_type == "application/pdf"
    assert content.parts[3].text == "receipts"
    assert content.parts[4].inline_data.mime_type == "image/png"


def test_screening_reads_the_requisition_from_the_first_part():
    request = LlmRequest(contents=[turn(REQUISITION, [file(), file(mime_type="image/jpeg")])])
    assert free_text(request) == ["LMS support", "for September"]


def test_send_is_only_ever_to_the_subject(monkeypatch):
    monkeypatch.setenv("WORKSPACE_SUBJECT", "lekkai@lekkacredit.com")
    sent = {}

    def call(scope, method, url, json):
        sent.update(scope=scope, raw=json["raw"])
        return type("R", (), {"json": lambda self: {"id": "m", "threadId": "t"}})()

    monkeypatch.setattr(gmail, "call", call)
    gmail.send_to_self("check", "hello")
    raw = gmail.base64.urlsafe_b64decode(sent["raw"]).decode()
    assert sent["scope"] == gmail.GMAIL_SEND
    assert "To: lekkai@lekkacredit.com" in raw


def image(fmt: str, size=(40, 30), mode="RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, "white").save(out, fmt)
    return out.getvalue()


@pytest.mark.parametrize(
    "fmt, mime_type", [("GIF", "image/gif"), ("BMP", "image/bmp"), ("TIFF", "image/tiff"), ("PNG", "image/x-png")]
)
def test_other_images_become_png(fmt, mime_type):
    data = image(fmt, mode="P" if fmt == "GIF" else "RGB")
    f = attachments.normalize(file(mime_type=mime_type, size=len(data)) | {"data": data})
    assert f["mimeType"] == "image/png"
    assert Image.open(io.BytesIO(f["data"])).format == "PNG"
    attachments.check([f])


def test_jpg_is_jpeg_untouched():
    data = image("JPEG")
    f = attachments.normalize(file(mime_type="image/jpg", size=len(data)) | {"data": data})
    assert f["mimeType"] == "image/jpeg"
    assert f["data"] == data


def test_a_large_photo_is_left_as_it_is():
    data = image("JPEG", size=(4000, 3000))
    f = attachments.normalize(file(mime_type="image/jpeg", size=len(data)) | {"data": data})
    assert f["data"] == data


def test_not_an_image_is_left_for_check():
    f = attachments.normalize(file(mime_type="application/msword"))
    assert f["mimeType"] == "application/msword"
    with pytest.raises(HTTPException):
        attachments.check([f])


@pytest.mark.parametrize(
    "body, want",
    [
        ('{"error": {"code": 404, "message": "File not found: X."}}', "File not found: X."),
        ("<html>Bad gateway</html>", "<html>Bad gateway</html>"),
        ('{"error": "invalid_grant"}', '{"error": "invalid_grant"}'),
    ],
)
def test_reason(body, want):
    response = type("R", (), {"text": body, "json": lambda self: json.loads(body)})()
    assert delegation.reason(response) == want
