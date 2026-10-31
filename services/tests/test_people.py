"""Someone's full name, from Workspace's directory, kept on users/{email} for a day and never forgotten."""

from datetime import UTC, datetime, timedelta

import pytest
import requests
from fastapi.testclient import TestClient

import store
from api import people
from api.main import app
from tests.firestore import Db

# Taken before conftest fakes it for every test
REAL = people.name
ADA = "ada@lekkacredit.com"


@pytest.fixture
def db(monkeypatch):
    db = Db()
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setattr(people, "name", REAL)
    monkeypatch.setattr(people, "_cache", {})
    return db


@pytest.fixture
def asked(monkeypatch):
    asked = []
    monkeypatch.setattr(people, "directory", lambda email: asked.append(email) or "Ada Moyo")
    return asked


def refused(email):
    raise requests.ConnectionError("no directory")


def test_a_name_comes_from_the_directory_and_is_kept(db, asked):
    assert people.name(ADA) == "Ada Moyo"
    assert db.docs[("users", ADA)]["name"] == "Ada Moyo"
    assert asked == [ADA]


def test_a_name_a_week_old_is_asked_again(db, asked):
    db.docs[("users", ADA)] = {"name": "Ada", "name_checked_at": datetime.now(UTC) - timedelta(days=8)}
    assert people.name(ADA) == "Ada Moyo" and asked == [ADA]


def test_a_name_under_a_week_old_isnt_asked_again(db, asked):
    db.docs[("users", ADA)] = {"name": "Ada", "name_checked_at": datetime.now(UTC) - timedelta(days=6)}
    assert people.name(ADA) == "Ada" and asked == []


def test_when_the_directory_cant_say_the_saved_name_stands(db, monkeypatch):
    db.docs[("users", ADA)] = {"name": "Ada", "name_checked_at": datetime.now(UTC) - timedelta(days=9)}
    monkeypatch.setattr(people, "directory", refused)
    assert people.name(ADA) == "Ada"
    assert db.docs[("users", ADA)]["name"] == "Ada"


def test_without_one_saved_its_no_name(db, monkeypatch):
    monkeypatch.setattr(people, "directory", refused)
    assert people.name(ADA) is None


def test_only_ours_are_looked_up(db, asked):
    assert people.name("someone@gmail.com") is None and asked == []


def test_the_ui_gets_a_name_or_none(monkeypatch, names):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", ADA)
    names[ADA] = "Ada Moyo"
    got = TestClient(app).get(f"/api/people/{ADA}").json()
    assert got == {"email": ADA, "name": "Ada Moyo"}
    assert TestClient(app).get("/api/people/bo@lekkacredit.com").json()["name"] is None
