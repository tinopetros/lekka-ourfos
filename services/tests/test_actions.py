"""Actions: the thread told first, then the action kept and the submission done; and the API that starts them."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_forms import Doc
from test_mifos import REQUISITION

import emails
import store
from api import groups
from api import people as names
from api.main import app
from common import execution_id
from integrations import workflows
from routers import actions
from tests.firestore import Db

DONE = {"kind": "done", "by": "tino@lekkacredit.com", "by_name": "Tino Petros", "comment": "Posted it by hand"}
BUCKET = "ourfos-dev-attachments"
FILE = f"gs://{BUCKET}/requisition/r/actions/ab12cd34.pdf"


@pytest.fixture
def docs(monkeypatch):
    docs = {("requisition", "r"): {"answers": REQUISITION, "thread": {"thread_id": "t1"}, "status": "handed_over"}}
    monkeypatch.setattr(store, "submission", lambda form, id: Doc(docs, (form, id)))
    monkeypatch.setattr(store, "action", lambda form, id, run: Doc(docs, (form, id, "actions", run)))
    monkeypatch.setenv("UI_URL", "https://ourfos.example")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", BUCKET)
    execution_id.set("run-9")
    return docs


@pytest.fixture
def sent(monkeypatch):
    sent = []

    def send(form, kind, submitter, sender, subject, html, text, thread=None, test=False):
        sent.append((kind, html, text, thread))
        return {"message_id": "m1", "thread_id": "t1"}

    monkeypatch.setattr(actions, "send", send)
    monkeypatch.setattr(emails, "form_name", lambda form: "Requisition Approval Request Form")
    return sent


def test_the_thread_hears_who_marked_it_done_how_and_its_files(docs, sent):
    actions.tell("requisition", "r", DONE | {"files": [FILE]})
    [(kind, html, text, thread)] = sent
    assert kind == "done" and thread == {"thread_id": "t1"}
    assert "Tino Petros marked this requisition done." in text and "Posted it by hand" in text
    assert "/api/files?ref=gs%3A%2F%2Fourfos-dev-attachments%2Frequisition%2Fr%2Factions%2Fab12cd34.pdf" in html
    assert "history" in text


def test_once_told_the_action_is_kept_and_the_requisition_is_done(docs):
    actions.record("requisition", "r", DONE | {"email": {"message_id": "m1", "thread_id": "t1"}})
    action = docs[("requisition", "r", "actions", "run-9")]
    assert (action["kind"], action["by"], action["comment"]) == ("done", "tino@lekkacredit.com", "Posted it by hand")
    assert action["email"]["message_id"] == "m1"
    assert docs[("requisition", "r")]["status"] == "done"


@pytest.mark.parametrize("change", [{"comment": "  "}, {"kind": "close"}, {"by": ""}])
def test_an_action_needs_its_kind_who_and_a_comment(docs, sent, change):
    with pytest.raises(HTTPException) as e:
        actions.tell("requisition", "r", DONE | change)
    assert e.value.status_code == 422 and not sent


TINO, ADA = "tino@lekkacredit.com", "ada@lekkacredit.com"


@pytest.fixture
def db(monkeypatch):
    db = Db()
    db.docs[("requisitions", "r")] = {"status": "handed_over"}
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setattr(groups, "of", lambda email: {"directors@lekkacredit.com"} if email == TINO else set())
    monkeypatch.setattr(names, "name", lambda email: "Tino Petros")
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", BUCKET)
    return db


@pytest.fixture
def started(monkeypatch):
    started = []
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: started.append((workflow, argument)) or "e1")
    return started


def as_(monkeypatch, email):
    monkeypatch.setenv("ACT_AS", email)
    return TestClient(app)


URL = "/api/forms/requisition/submissions/r/actions"


def test_a_director_marks_a_handed_over_requisition_done_through_the_action_workflow(db, started, monkeypatch):
    response = as_(monkeypatch, TINO).post(
        URL, json={"kind": "done", "comment": " Posted it by hand ", "files": [FILE]}
    )
    assert response.json() == {"run": "e1"}
    [(workflow, argument)] = started
    assert workflow == "action"
    assert argument == {
        "form": "requisition",
        "id": "r",
        "kind": "done",
        "by": TINO,
        "by_name": "Tino Petros",
        "comment": "Posted it by hand",
        "files": [FILE],
    }


def test_nobody_else_may(db, started, monkeypatch):
    assert as_(monkeypatch, ADA).post(URL, json={"kind": "done", "comment": "Done"}).status_code == 403 and not started


def test_only_a_handed_over_one_with_a_comment_and_its_own_files(db, started, monkeypatch):
    client = as_(monkeypatch, TINO)
    assert client.post(URL, json={"kind": "done", "comment": " "}).status_code == 422
    assert (
        client.post(
            URL, json={"kind": "done", "comment": "Done", "files": [f"gs://{BUCKET}/requisition/x/a.pdf"]}
        ).status_code
        == 422
    )
    db.docs[("requisitions", "r")]["status"] = "done"
    assert client.post(URL, json={"kind": "done", "comment": "Done"}).status_code == 409
    assert not started


def test_an_action_is_done_once_recorded_and_failed_with_its_runs_reason(db, monkeypatch):
    client = as_(monkeypatch, TINO)
    monkeypatch.setattr(workflows, "state", lambda workflow, run: ("ACTIVE", None))
    assert client.get("/api/forms/requisition/submissions/r/actions/e1").json() == {"state": "running", "reason": None}
    monkeypatch.setattr(workflows, "state", lambda workflow, run: ("FAILED", "gmail: 500"))
    assert client.get("/api/forms/requisition/submissions/r/actions/e1").json() == {
        "state": "failed",
        "reason": "gmail: 500",
    }
    db.docs[("requisitions/r/actions", "e1")] = {"kind": "done"}
    assert client.get("/api/forms/requisition/submissions/r/actions/e1").json()["state"] == "done"


def test_a_submission_shows_its_actions_newest_first(db, monkeypatch):
    db.docs[("requisitions/r/actions", "e1")] = {
        "kind": "done",
        "by": TINO,
        "comment": "Posted it by hand",
        "at": datetime(2026, 10, 31, tzinfo=UTC),
    }
    shown = as_(monkeypatch, TINO).get("/api/forms/requisition/submissions/r").json()["actions"]
    assert [(a["id"], a["kind"], a["comment"]) for a in shown] == [("e1", "done", "Posted it by hand")]


LOANS = "/api/forms/loan_approval/submissions/l/actions"


def test_a_director_approves_without_a_word_but_disapproves_with_one(db, started, monkeypatch):
    db.docs[("loan_approvals", "l")] = {"status": "done"}
    client = as_(monkeypatch, TINO)
    assert client.post(LOANS, json={"kind": "approve"}).status_code == 200
    assert client.post(LOANS, json={"kind": "disapprove"}).status_code == 422
    assert client.post(LOANS, json={"kind": "disapprove", "comment": "Too large"}).status_code == 200
    assert [a["kind"] for _, a in started] == ["approve", "disapprove"]


def test_a_decided_one_isnt_decided_again_but_anyone_may_comment(db, started, monkeypatch):
    db.docs[("loan_approvals", "l")] = {"status": "approved"}
    assert as_(monkeypatch, TINO).post(LOANS, json={"kind": "disapprove", "comment": "No"}).status_code == 409
    assert as_(monkeypatch, ADA).post(LOANS, json={"kind": "approve"}).status_code == 403
    assert as_(monkeypatch, ADA).post(LOANS, json={"kind": "comment", "comment": "Checked"}).status_code == 200


def test_a_requisition_is_neither_approved_nor_commented_on(db, started, monkeypatch):
    assert as_(monkeypatch, TINO).post(URL, json={"kind": "approve"}).status_code == 403
    assert as_(monkeypatch, TINO).post(URL, json={"kind": "comment", "comment": "Hi"}).status_code == 403


@pytest.mark.parametrize(
    ("kind", "status", "said"),
    [
        ("approve", "approved", "approved this"),
        ("disapprove", "disapproved", "disapproved this"),
        ("comment", None, "commented on this"),
    ],
)
def test_each_kind_says_what_it_did_and_leaves_its_status(docs, sent, kind, status, said):
    docs[("loan_approval", "l")] = {"answers": {}, "thread": {"thread_id": "t2"}, "status": "done"}
    actions.tell("loan_approval", "l", DONE | {"kind": kind})
    assert f"Tino Petros {said} loan approval request." in sent[-1][2]
    actions.record("loan_approval", "l", DONE | {"kind": kind})
    assert docs[("loan_approval", "l")]["status"] == (status or "done")


def test_a_requisition_disapproved_has_its_live_entry_reversed_first(db, started, monkeypatch):
    db.docs[("requisitions", "r")] = {"status": "done", "live_entry": "L1"}
    assert as_(monkeypatch, TINO).post(URL, json={"kind": "disapprove", "comment": "Not ours"}).status_code == 200
    [(_, argument)] = started
    assert argument["transaction_id"] == "L1" and argument["kind"] == "disapprove"


def test_one_with_nothing_live_is_only_disapproved(db, started, monkeypatch):
    db.docs[("requisitions", "r")] = {"status": "handed_over"}
    as_(monkeypatch, TINO).post(URL, json={"kind": "disapprove", "comment": "Not ours"})
    assert "transaction_id" not in started[0][1]


def test_its_email_names_the_reversal(docs, sent):
    actions.tell("requisition", "r", DONE | {"kind": "disapprove", "reversal": {"entry": "L1", "by": "L2"}})
    text = sent[-1][2]
    assert "disapproved this requisition." in text and "Reversed: L1" in text and "By transaction: L2" in text
