"""Submitting from our own form, against a store in memory: checked, numbered once, stored, and its workflow started."""

import pytest
from fastapi.testclient import TestClient

import store
from api import submit
from api.main import app
from integrations import workflows
from tests.firestore import Db

TRIP = {
    "vehicle": "White Nissan Note | AGO8747",
    "date": "2026-10-27",
    "purpose": "Client visit",
    "odometer_start": 100,
    "odometer_end": 140,
}


@pytest.fixture
def db(monkeypatch):
    db = Db()
    monkeypatch.setattr(store, "client", lambda: db)
    # Firestore's own retries a transaction against the real thing: here, it's only called
    monkeypatch.setattr(submit, "transactional", lambda f: f)
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "driver@lekkacredit.com")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    return db


@pytest.fixture
def started(monkeypatch):
    runs = []
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: runs.append((workflow, argument)) or "e1")
    return runs


def post(id="t1", answers=TRIP, **body):
    return TestClient(app).post(f"/api/forms/vehicle_log/submissions/{id}/submit", json={"answers": answers} | body)


def test_a_submission_is_stored_numbered_and_started(db, started):
    got = post()
    assert got.status_code == 200 and got.json() == {"id": "t1", "response_number": -1}
    doc = db.docs[("vehicle_logs", "t1")]
    assert (doc["source"], doc["submitted_by"], doc["status"], doc["execution_id"]) == (
        "ourfos",
        "driver@lekkacredit.com",
        "received",
        "e1",
    )
    assert doc["answers"]["date"] == "2026-10-27" and doc["answers"]["source"] == "ourfos"
    [(workflow, argument)] = started
    assert workflow == "intake" and argument["submission"]["purpose"] == "Client visit"
    assert (argument["test"], argument["mifos"]) == (False, False)


def test_dev_counts_down_past_what_it_has_and_prod_up(db, started, monkeypatch):
    db.docs[("vehicle_logs", "old")] = {"response_number": -482}
    assert post("a").json()["response_number"] == -483
    assert post("b").json()["response_number"] == -484
    assert submit.first([12, 3], up=True) == 13 and submit.first([], up=True) == 1


def test_submitting_twice_is_submitting_once(db, started):
    assert post().json() == post().json()
    assert len(started) == 1


def test_a_workflow_that_didnt_start_is_started_on_the_next_try(db, started, monkeypatch):
    def down(workflow, argument):
        raise RuntimeError("workflows is down")

    monkeypatch.setattr(workflows, "start", down)
    with pytest.raises(RuntimeError):
        post()
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: started.append(workflow) or "e2")
    assert post().json()["response_number"] == -1
    assert db.docs[("vehicle_logs", "t1")]["execution_id"] == "e2"


def test_someone_elses_id_is_refused(db, started):
    db.docs[("vehicle_logs", "t1")] = {"status": "received", "submitted_by": "else@lekkacredit.com"}
    assert post().status_code == 409


def test_what_doesnt_fit_the_form_is_refused_by_its_field(db, started):
    got = post(answers=TRIP | {"odometer_end": 99, "vehicle": "A bicycle"})
    assert got.status_code == 422
    assert [e["loc"] for e in got.json()["detail"]] == [["vehicle"], ["odometer_end"]]
    got = post(answers=TRIP | {"odometer_end": 99})
    assert "Below the odometer at start" in got.json()["detail"][0]["msg"] and not started


def test_an_id_firestore_cant_take_is_refused(db, started):
    assert post("a.b").status_code == 400


def test_a_test_needs_its_permission(db, started, groups_of):
    assert post(test=True).status_code == 403 and not started
    groups_of["driver@lekkacredit.com"] = {"tech@lekkacredit.com"}
    assert post(test=True).status_code == 200
    assert started[0][1]["test"] is True and db.docs[("vehicle_logs", "t1")]["test"] is True
