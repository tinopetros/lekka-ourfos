import os

import pytest
from fastapi import HTTPException
from google.adk.models import LlmRequest
from google.cloud import modelarmor_v1

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
    request = LlmRequest(contents=[turn(REQUISITION, [file(), file(mime_type="image/jpeg")])])
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
