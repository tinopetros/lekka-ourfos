"""A requisition's live entry undone from the UI: the correction workflow, asked for a reversal only."""

import pytest
from fastapi.testclient import TestClient

import store
from api.main import app
from integrations import workflows
from tests.firestore import Db

URL = "/api/forms/requisition/submissions/r1/reverse"
ADA = "ada@lekkacredit.com"


@pytest.fixture
def started(monkeypatch, groups_of):
    db = Db()
    db.docs[("requisitions", "r1")] = {"live_entry": "T1", "answers": {}}
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", ADA)
    groups_of[ADA] = {"directors@lekkacredit.com"}
    runs = []
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: runs.append((workflow, argument)) or "e1")
    return runs


def test_a_reversal_starts_a_correction_with_no_lines(started):
    got = TestClient(app).post(URL, json={"transaction_id": "T1", "reason": " Paid twice "})
    assert got.status_code == 200 and got.json() == {"run": "e1"}
    assert started == [
        ("correction", {"id": "r1", "reason": "Paid twice", "requested_by": ADA, "transaction_id": "T1"})
    ]


def test_only_the_live_entry_is_reversed(started):
    assert TestClient(app).post(URL, json={"transaction_id": "T0", "reason": "x"}).status_code == 409
    assert started == []


def test_a_reversal_says_why(started):
    assert TestClient(app).post(URL, json={"transaction_id": "T1", "reason": "  "}).status_code == 422
    assert started == []


def test_only_directors_reverse(started, groups_of):
    groups_of[ADA] = set()
    assert TestClient(app).post(URL, json={"transaction_id": "T1", "reason": "x"}).status_code == 403
    assert started == []
