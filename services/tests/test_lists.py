"""Lists, against a store in memory: tests left out unless whoever may make them asks for them, pages full either way."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import journal
import store
from api import groups
from api.main import app
from tests.firestore import Db

ADA, TINO = "ada@lekkacredit.com", "tino@lekkacredit.com"
START = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
def db(monkeypatch):
    db = Db()
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setattr(
        groups, "of", lambda email: {"tech@lekkacredit.com", "directors@lekkacredit.com"} if email == TINO else set()
    )
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    return db


def as_(monkeypatch, email):
    monkeypatch.setenv("ACT_AS", email)
    return TestClient(app)


def requisitions(db, *tests):
    """One a minute, the first newest, each a test or not"""
    for i, test in enumerate(tests):
        db.docs[("requisitions", f"r{i}")] = {
            "received_at": START - timedelta(minutes=i),
            "test": test,
            "status": "done",
        }


def ids(response):
    return [s["id"] for s in response.json()["items"]]


def test_tests_are_left_out_and_a_page_is_still_full(db, monkeypatch):
    requisitions(db, True, False, True, True, False, False)
    client = as_(monkeypatch, ADA)
    first = client.get("/api/forms/requisition/submissions", params={"limit": 2}).json()
    assert [s["id"] for s in first["items"]] == ["r1", "r4"] and first["next"] == "r4"
    rest = client.get("/api/forms/requisition/submissions", params={"limit": 2, "cursor": "r4"}).json()
    assert [s["id"] for s in rest["items"]] == ["r5"] and rest["next"] is None


def test_whoever_may_make_tests_may_show_them(db, monkeypatch):
    requisitions(db, True, False)
    assert ids(as_(monkeypatch, TINO).get("/api/forms/requisition/submissions", params={"tests": True})) == ["r0", "r1"]


def test_nobody_else_may(db, monkeypatch):
    requisitions(db, True, False)
    response = as_(monkeypatch, ADA).get("/api/forms/requisition/submissions", params={"tests": True})
    assert response.status_code == 403


def test_a_test_submissions_entries_are_tests(db, monkeypatch):
    db.docs[("requisitions", "r0")] = {"test": True}
    monkeypatch.setattr(store, "NOW", START)
    journal.posted("requisition", "r0", "run", "t1", [], [], START.date(), "ref", "said")
    assert db.docs[("journal_entries", "t1")]["test"] is True


def test_an_entry_from_before_entries_said_is_a_test_if_its_submission_is(db, monkeypatch):
    db.docs[("requisitions", "r0")] = {"test": True}
    db.docs[("requisitions", "r1")] = {"test": False}
    db.docs[("journal_entries", "t0")] = {"recorded_at": START, "form": "requisition", "submission": "r0"}
    db.docs[("journal_entries", "t1")] = {
        "recorded_at": START - timedelta(minutes=1),
        "form": "requisition",
        "submission": "r1",
    }
    db.docs[("journal_entries", "t2")] = {"recorded_at": START - timedelta(minutes=2), "test": True}
    db.docs[("journal_entries", "t3")] = {"recorded_at": START - timedelta(minutes=3), "source": "mifos"}
    entries = as_(monkeypatch, TINO).get("/api/journal_entries").json()["items"]
    assert [e["transaction_id"] for e in entries] == ["t1", "t3"]
    shown = as_(monkeypatch, TINO).get("/api/journal_entries", params={"tests": True}).json()["items"]
    assert [(e["transaction_id"], e["test"]) for e in shown] == [
        ("t0", True),
        ("t1", False),
        ("t2", True),
        ("t3", False),
    ]
