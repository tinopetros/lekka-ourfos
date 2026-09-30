import asyncio
import threading

import pytest

from classify import attachments
from integrations.workspace import delegation, drive
from integrations.workspace.delegation import WorkspaceError
from requisition import Requisition


class Response:
    def __init__(self, data=b"%PDF-1.4", content_type="application/pdf; charset=binary"):
        self.content, self.headers = data, {"Content-Type": content_type}


def test_a_file_is_one_call(monkeypatch):
    calls = []

    def call(scope, method, url, params):
        calls.append((url, params))
        return Response()

    monkeypatch.setattr(drive, "call", call)
    assert drive.fetch("A1") == {"id": "A1", "mimeType": "application/pdf", "size": 8, "data": b"%PDF-1.4"}
    assert calls == [(f"{drive.DRIVE_FILES}/A1", {"alt": "media"})]


def test_a_google_doc_is_exported_as_pdf(monkeypatch):
    def call(scope, method, url, params):
        if params == {"alt": "media"}:
            raise WorkspaceError(403, "403 Only files with binary content can be downloaded", "fileNotDownloadable")
        assert url.endswith("/A1/export")
        return Response(content_type="text/html")

    monkeypatch.setattr(drive, "call", call)
    assert drive.fetch("A1")["mimeType"] == "application/pdf"


def test_any_other_refusal_is_raised(monkeypatch):
    def call(scope, method, url, params):
        raise WorkspaceError(404, "404 File not found: A1.", "notFound")

    monkeypatch.setattr(drive, "call", call)
    with pytest.raises(WorkspaceError) as e:
        drive.fetch("A1")
    assert e.value.status == 404


@pytest.mark.parametrize(
    "body, want",
    [
        ({"error": {"errors": [{"reason": "fileNotDownloadable"}]}}, "fileNotDownloadable"),
        ({"error": {"message": "no reasons"}}, None),
        (ValueError, None),
    ],
)
def test_code(body, want):
    class R:
        def json(self):
            if body is ValueError:
                raise ValueError
            return body

    assert delegation.code(R()) == want


def test_files_are_fetched_at_once_and_kept_in_field_order(monkeypatch):
    # Every fetch waits for all three to have started: fetched one by one, this would never finish
    started = threading.Barrier(3, timeout=5)

    def fetch(file_id):
        started.wait()
        return {"id": file_id, "mimeType": "application/pdf", "size": 1, "data": b"%"}

    monkeypatch.setattr(drive, "fetch", fetch)
    requisition = Requisition(
        response_number=-482,
        response_id="r",
        submitted_by="lekkai@lekkacredit.com",
        submitted_at="2026-09-28T21:34:33Z",
        payable_to="x",
        amount=1,
        files={"signed_requisition_form": ["A1"], "receipts": ["B1", "B2"]},
    )
    files = asyncio.run(attachments.load(requisition))
    assert [(f["field"], f["id"]) for f in files] == [
        ("signed_requisition_form", "A1"),
        ("receipts", "B1"),
        ("receipts", "B2"),
    ]
