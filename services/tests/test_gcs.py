import asyncio
import os

import pytest
from fastapi import HTTPException

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from classify import attachments
from integrations import gcs
from requisition import Requisition

OURS = "gs://ourfos-dev-attachments/evals/requisitions/a/receipts/0f1e"


class Response:
    def __init__(self, status=200, data=b"%PDF-1.4", content_type="application/pdf", text=""):
        self.status_code, self.ok = status, status < 400
        self.content, self.text, self.headers = data, text, {"Content-Type": content_type}

    def json(self):
        return {"error": {"message": self.text}}


@pytest.fixture
def got(monkeypatch):
    monkeypatch.setenv("ATTACHMENTS_BUCKET", "ourfos-dev-attachments")
    calls = []

    def use(response):
        def get(url, params, timeout):
            calls.append(url)
            return response

        monkeypatch.setattr(gcs, "session", lambda: type("S", (), {"get": staticmethod(get)})())
        return calls

    return use


def test_fetch_reads_type_and_bytes_in_one_call(got):
    calls = got(Response(content_type="image/jpeg; charset=binary", data=b"jpeg"))
    assert gcs.fetch(OURS) == {"id": OURS, "mimeType": "image/jpeg", "size": 4, "data": b"jpeg"}
    assert calls == [
        "https://storage.googleapis.com/storage/v1/b/ourfos-dev-attachments/o/evals%2Frequisitions%2Fa%2Freceipts%2F0f1e"
    ]


@pytest.mark.parametrize("ref", ["gs://someone-elses/receipt.pdf", "gs://ourfos-prod-attachments/x"])
def test_only_our_bucket(got, ref):
    calls = got(Response())
    with pytest.raises(gcs.GcsError) as e:
        gcs.fetch(ref)
    assert e.value.status == 403
    assert calls == []


@pytest.mark.parametrize("ref", ["gs://", "gs://bucket", "gs://bucket/"])
def test_not_a_ref(got, ref):
    with pytest.raises(gcs.GcsError):
        gcs.fetch(ref)


def load(**files):
    requisition = Requisition(
        response_number=1,
        response_id="r",
        submitted_by="a@lekkacredit.com",
        submitted_at="2026-03-06T12:40:10Z",
        payable_to="x",
        amount=1,
        files=files,
    )
    return asyncio.run(attachments.load(requisition))


def test_load_routes_gs_refs_to_the_bucket(got):
    got(Response())
    [f] = load(receipts=[OURS])
    assert (f["field"], f["id"], f["mimeType"]) == ("receipts", OURS, "application/pdf")


@pytest.mark.parametrize("status, want", [(404, 422), (403, 422), (503, 503), (429, 429)])
def test_load_maps_errors_as_drive_does(got, status, want):
    got(Response(status=status, text="No such object"))
    with pytest.raises(HTTPException) as e:
        load(receipts=[OURS])
    assert e.value.status_code == want
    assert OURS in e.value.detail


def test_load_hands_over_another_bucket(got):
    with pytest.raises(HTTPException) as e:
        load(receipts=["gs://someone-elses/receipt.pdf"])
    assert e.value.status_code == 422
