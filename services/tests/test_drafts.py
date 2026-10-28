"""Drafts, against a store in memory: saved as they're filled in, only their author's, and submitted once."""

import re

import pytest
from fastapi.testclient import TestClient

import store
from api import submit
from api.main import app
from integrations import gcs, workflows
from tests.firestore import Db

BUCKET = "ourfos-dev-attachments"
URL = "/api/forms/write_off/submissions/w1"
# A write-off with every answer it needs
ANSWERS = {
    "client_first_name": "Ada",
    "client_last_name": "Moyo",
    "client_number": "000123",
    "loan_account_number": "000456",
    "original_principal": 600,
    "original_interest": 120,
    "loan_term": 12,
    "total_recovered": 1110,
    "current_balance": 212.52,
    "justification": "No longer employed: deductions stopped",
}


@pytest.fixture
def db(monkeypatch):
    db = Db()
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setattr(submit, "transactional", lambda f: f)
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: "e1")
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "ada@lekkacredit.com")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", BUCKET)
    return db


@pytest.fixture
def bucket(monkeypatch):
    objects = {}

    def upload(name, data, content_type):
        objects[name] = (data, content_type)
        return f"gs://{BUCKET}/{name}"

    def delete_prefix(prefix):
        gone = [n for n in objects if n.startswith(prefix)]
        for n in gone:
            del objects[n]
        return len(gone)

    monkeypatch.setattr(gcs, "upload", upload)
    monkeypatch.setattr(gcs, "delete_prefix", delete_prefix)
    return objects


def client(who="ada@lekkacredit.com", monkeypatch=None):
    if monkeypatch:
        monkeypatch.setenv("ACT_AS", who)
    return TestClient(app)


def test_a_draft_takes_anything_as_typed_and_stays_out_of_lists(db):
    got = client().put(URL, json={"values": {"client_first_name": "Ada", "total_recovered": "12.3"}})
    assert got.status_code == 200 and got.json()["title"] == "Ada"
    doc = db.docs[("write_offs", "w1")]
    assert (doc["status"], doc["submitted_by"], doc["draft"]["total_recovered"]) == (
        "draft",
        "ada@lekkacredit.com",
        "12.3",
    )
    assert "received_at" not in doc and "response_number" not in doc


def test_a_draft_opens_with_its_values_for_its_author_only(db, monkeypatch):
    client().put(URL, json={"values": {"client_first_name": "Ada"}})
    assert client().get(URL).json()["draft"] == {"client_first_name": "Ada"}
    other = client("bo@lekkacredit.com", monkeypatch)
    assert other.get(URL).status_code == 404
    assert other.put(URL, json={"values": {}}).status_code == 403


def test_your_drafts_are_yours(db, monkeypatch):
    client().put(URL, json={"values": {"client_first_name": "Ada"}})
    client("bo@lekkacredit.com", monkeypatch).put(
        "/api/forms/write_off/submissions/w2", json={"values": {"client_first_name": "Bo"}}
    )
    monkeypatch.setenv("ACT_AS", "ada@lekkacredit.com")
    assert [d["id"] for d in client().get("/api/forms/write_off/drafts").json()] == ["w1"]


def test_a_draft_once_submitted_is_no_longer_one(db):
    client().put(URL, json={"values": {"client_first_name": "Ada"}})
    assert client().post(f"{URL}/submit", json={"answers": ANSWERS}).status_code == 200
    doc = db.docs[("write_offs", "w1")]
    assert doc["status"] == "received" and "draft" not in doc and doc["response_number"] == -1
    assert client().put(URL, json={"values": {}}).status_code == 409
    assert client().delete(URL).status_code == 409


def test_a_file_goes_under_its_draft_named_afresh_its_extension_kept(db, bucket):
    got = client().post(
        f"{URL}/files",
        params={"name": "bank statement (1).pdf"},
        content=b"%PDF",
        headers={"content-type": "application/pdf"},
    )
    ref = got.json()["ref"]
    assert re.fullmatch(rf"gs://{BUCKET}/write_off/w1/[0-9a-f]{{8}}\.pdf", ref)
    # The first thing done on it makes the draft
    assert db.docs[("write_offs", "w1")]["status"] == "draft"
    assert list(bucket.values()) == [(b"%PDF", "application/pdf")]


def test_a_submission_names_only_its_own_files(db, bucket):
    ref = client().post(f"{URL}/files", params={"name": "a.pdf"}, content=b"x").json()["ref"]
    answers = ANSWERS
    stray = answers | {"supporting_documents": [f"gs://{BUCKET}/write_off/w9/x-a.pdf"]}
    got = client().post(f"{URL}/submit", json={"answers": stray})
    assert got.status_code == 422 and got.json()["detail"][0]["loc"] == ["supporting_documents"]
    assert (
        client().post(f"{URL}/submit", json={"answers": answers | {"supporting_documents": [ref]}}).status_code == 200
    )


def test_a_discarded_draft_takes_its_files_with_it(db, bucket):
    client().post(f"{URL}/files", params={"name": "a.pdf"}, content=b"x")
    assert client().delete(URL).status_code == 204
    assert ("write_offs", "w1") not in db.docs and bucket == {}


def test_a_draft_cant_be_a_test_without_its_permission(db):
    assert client().put(URL, json={"values": {}, "test": True}).status_code == 403


def test_a_draft_is_looked_over_as_its_saved_and_saved_whatever_it_finds(db):
    answers = {k: v for k, v in ANSWERS.items() if k != "client_last_name"} | {"total_recovered": 12.345}
    got = client().put(
        URL, json={"values": {"client_first_name": "Ada", "total_recovered": "12.345"}, "answers": answers}
    )
    assert got.status_code == 200
    assert {tuple(p["loc"]) for p in got.json()["problems"]} == {("client_last_name",), ("total_recovered",)}
    assert db.docs[("write_offs", "w1")]["draft"]["total_recovered"] == "12.345"


def test_a_trips_odometer_going_backwards_shows_as_its_drafted(db):
    answers = {"vehicle": "White Nissan Note | AGO8747", "date": "2026-10-28", "purpose": "x", "odometer_start": 100}
    got = client().put(
        "/api/forms/vehicle_log/submissions/v1", json={"values": {}, "answers": answers | {"odometer_end": 1}}
    )
    assert got.json()["problems"] == [{"loc": ["odometer_end"], "msg": "Below the odometer at start"}]
