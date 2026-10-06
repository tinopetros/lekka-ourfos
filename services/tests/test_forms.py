"""The steps every form shares, against a store in memory: one first email a submission, whichever run."""

import pytest
from fastapi import HTTPException

import store
from common import execution_id
from routers import forms

SUBMISSION = {
    "response_number": -482,
    "response_id": "r",
    "submitted_by": "lekkai@lekkacredit.com",
    "submitted_at": "2026-04-10T13:45:12Z",
    "trip_name_purpose": "CBD",
}


class Doc:
    def __init__(self, docs, path):
        self.docs, self.path = docs, path
        self.ref = type("Ref", (), {"id": path[-1]})()

    def get(self):
        if self.path not in self.docs:
            raise HTTPException(404, "missing")
        return self.docs[self.path]

    def save(self, **fields):
        self.docs.setdefault(self.path, {}).update(fields)

    record = save


@pytest.fixture
def docs(monkeypatch):
    docs = {}
    monkeypatch.setattr(store, "submission", lambda form, id: Doc(docs, (form, id)))
    monkeypatch.setattr(store, "run", lambda form, id, run: Doc(docs, (form, id, run)))
    monkeypatch.setattr(forms.gmail, "rfc822_id", lambda message_id: f"<{message_id}@mail>")
    execution_id.set("run-1")
    return docs


@pytest.fixture
def sent(monkeypatch):
    sent = []

    def send(form, kind, *args, **kwargs):
        sent.append(kind)
        return {"message_id": f"m{len(sent)}", "thread_id": "t1"}

    monkeypatch.setattr(forms, "send", send)
    monkeypatch.setattr(forms.emails, "form_name", lambda form: "Vehicle Log Form")
    return sent


def test_receive_keeps_the_submission_and_starts_the_run(docs):
    forms.receive("vehicle_log", "r", {"submission": SUBMISSION, "raw": {"x": "y"}, "workflow": "intake"})
    assert docs[("vehicle_log", "r")]["answers"]["trip_name_purpose"] == "CBD"
    assert docs[("vehicle_log", "r")]["raw"] == {"x": "y"}
    assert docs[("vehicle_log", "r", "run-1")]["status"] == "received"
    assert docs[("vehicle_log", "r", "run-1")]["workflow"] == "intake"
    assert "mifos" not in docs[("vehicle_log", "r", "run-1")]


def test_a_run_keeps_mifos_only_when_its_off(docs):
    forms.receive("vehicle_log", "r", {"submission": SUBMISSION, "mifos": False})
    assert docs[("vehicle_log", "r", "run-1")]["mifos"] is False


def test_a_second_run_finds_the_thread_and_sends_no_first_email(docs, sent):
    forms.receive("vehicle_log", "r", {"submission": SUBMISSION})
    first = forms.acknowledge("vehicle_log", "r", {})
    execution_id.set("run-2")
    assert forms.acknowledge("vehicle_log", "r", {}) == first == {"thread_id": "t1", "in_reply_to": "<m1@mail>"}
    assert sent == ["acknowledgement"]


def test_a_handover_is_sent_when_the_database_cant_be_read(docs, sent):
    forms.handover("vehicle_log", "r", {"error": "boom", "submission": SUBMISSION})
    assert sent == ["handover"]
    assert "handover" in docs[("vehicle_log", "r", "run-1")]["emails"]


def test_a_form_that_couldnt_be_read_is_kept_raw(docs, sent):
    forms.handover("vehicle_log", "exec", {"error": "trip_name_purpose: field required", "raw": {"a": "b"}})
    assert docs[("vehicle_log", "exec")]["raw"] == {"a": "b"}


def test_an_unknown_form_is_a_404(docs):
    with pytest.raises(HTTPException) as e:
        forms.acknowledge("payslip", "r", {})
    assert e.value.status_code == 404


def test_every_step_needs_its_run(docs):
    execution_id.set(None)
    with pytest.raises(HTTPException) as e:
        forms.receive("vehicle_log", "r", {"submission": SUBMISSION})
    assert e.value.status_code == 400
