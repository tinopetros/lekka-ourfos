import io
import json
import os

import pytest
from fastapi import HTTPException
from google.adk.models import LlmRequest
from google.cloud import modelarmor_v1
from PIL import Image

# The agent reads its template at import. Nothing here calls Model Armor
os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

import attachments
import google_workspace
from expenser.screen import documents, free_text
from expenser_runner import turn
from requisition import Requisition

REQUISITION = Requisition(
    response_number=482,
    response_id="r",
    submitted_by="ltanga@lekkacredit.com",
    payable_to="LMS support",
    amount=60,
    comment="for September",
    files={"signed_requisition_form": ["A1"], "receipts": ["B2"]},
)


def file(field="receipts", mime_type="application/pdf", size=10, name="receipt.pdf", id="B2"):
    return {"field": field, "id": id, "name": name, "mimeType": mime_type, "size": size, "data": b"x" * size}


@pytest.mark.parametrize("mime_type", sorted(google_workspace.SHOWN))
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
    half = google_workspace.MAX_BYTES // 2 + 1
    with pytest.raises(HTTPException) as e:
        attachments.check([file(size=half), file(size=half)])
    assert e.value.status_code == 422


def test_seen_keeps_no_bytes():
    assert attachments.seen([file()]) == [
        {"field": "receipts", "id": "B2", "name": "receipt.pdf", "mimeType": "application/pdf", "size": 10}
    ]


def test_turn():
    content = turn(REQUISITION, [file("signed_requisition_form", name="req.pdf"), file(mime_type="image/png")])
    assert content.parts[0].text.startswith('{"response_number": 482')
    assert content.parts[1].text == "signed_requisition_form: req.pdf"
    assert content.parts[2].inline_data.mime_type == "application/pdf"
    assert content.parts[3].text == "receipts: receipt.pdf"
    assert content.parts[4].inline_data.mime_type == "image/png"


def test_screening_reads_the_first_part_and_pdfs_only():
    request = LlmRequest(contents=[turn(REQUISITION, [file(size=100), file(mime_type="image/jpeg")])])
    assert free_text(request) == ["LMS support", "for September"]
    screened = documents(request)
    assert len(screened) == 1
    assert screened[0].byte_item.byte_data_type == modelarmor_v1.ByteDataItem.ByteItemType.PDF


def test_send_is_only_ever_to_the_subject(monkeypatch):
    monkeypatch.setenv("WORKSPACE_SUBJECT", "lekkai@lekkacredit.com")
    sent = {}

    def call(scope, method, url, json):
        sent.update(scope=scope, raw=json["raw"])
        return type("R", (), {"json": lambda self: {"id": "m", "threadId": "t"}})()

    monkeypatch.setattr(google_workspace, "call", call)
    google_workspace.send_to_self("check", "hello")
    raw = google_workspace.base64.urlsafe_b64decode(sent["raw"]).decode()
    assert sent["scope"] == google_workspace.GMAIL_SEND
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


def test_pdfs_outside_model_armors_limits_pass_unscreened(monkeypatch):
    from expenser import screen

    monkeypatch.setattr(screen, "SCREENABLE_BYTES", range(69, 100))
    request = LlmRequest(contents=[turn(REQUISITION, [file(size=50), file(size=80), file(size=200)])])
    assert len(documents(request)) == 1


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
    assert google_workspace.reason(response) == want
