"""Who may do what: every route names its permission, and the policy grants them."""

import pytest
from fastapi.testclient import TestClient

from api import permissions
from api.main import app
from api.permissions import allowed, granted


@pytest.fixture
def policy(monkeypatch):
    def use(policy):
        monkeypatch.setattr(permissions, "POLICY", policy)

    return use


def test_everyone_at_lekka_reads_and_submits_tech_tests_and_directors_read_the_journal(groups_of):
    groups_of["ada@lekkacredit.com"] = {"tech@lekkacredit.com"}
    groups_of["bo@lekkacredit.com"] = {"directors@lekkacredit.com"}
    assert allowed("anyone@lekkacredit.com", "forms:vehicle_log:submit")
    assert not allowed("anyone@lekkacredit.com", "forms:vehicle_log:test")
    assert not allowed("anyone@lekkacredit.com", "journal_entries:read")
    assert allowed("ada@lekkacredit.com", "forms:vehicle_log:test")
    assert allowed("bo@lekkacredit.com", "journal_entries:read")
    assert not allowed("someone@gmail.com", "forms:requisition:read")


def test_a_grant_is_to_a_person_a_domain_or_a_group(policy, groups_of):
    policy({"forms:requisition:*": ["user:Ada@lekkacredit.com", "group:Finance@lekkacredit.com"]})
    groups_of["bo@lekkacredit.com"] = {"finance@lekkacredit.com"}
    assert allowed("ada@lekkacredit.com", "forms:requisition:submit")
    assert not allowed("ada@lekkacredit.com", "forms:write_off:submit")
    assert allowed("bo@lekkacredit.com", "forms:requisition:submit")
    assert not allowed("finance@lekkacredit.com", "forms:requisition:submit")


def test_an_exclusion_wins_over_any_grant(policy, groups_of, monkeypatch):
    policy({"journal_entries:read": ["group:directors@lekkacredit.com"]})
    monkeypatch.setattr(permissions, "EXCLUDE", {"journal_entries:*": ["user:bo@lekkacredit.com"]})
    groups_of["ada@lekkacredit.com"] = groups_of["bo@lekkacredit.com"] = {"directors@lekkacredit.com"}
    assert allowed("ada@lekkacredit.com", "journal_entries:read")
    assert not allowed("bo@lekkacredit.com", "journal_entries:read")
    assert "journal_entries:read" not in granted("bo@lekkacredit.com")


def test_lekkai_reads_no_journal_even_as_a_director(groups_of):
    groups_of["lekkai@lekkacredit.com"] = {"directors@lekkacredit.com"}
    assert not allowed("lekkai@lekkacredit.com", "journal_entries:read")
    assert allowed("lekkai@lekkacredit.com", "forms:requisition:read")


def test_me_lists_what_you_may_do(monkeypatch, groups_of):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "anyone@lekkacredit.com")
    mine = TestClient(app).get("/api/me").json()["permissions"]
    assert "forms:requisition:submit" in mine and "files:read" in mine and "journal_entries:read" not in mine
    assert not [p for p in mine if p.endswith(":test")]
    groups_of["ada@lekkacredit.com"] = {"tech@lekkacredit.com"}
    assert "forms:requisition:test" in granted("ada@lekkacredit.com")


def test_a_route_without_its_permission_is_a_403(monkeypatch, policy):
    policy({"forms:requisition:read": ["domain:lekkacredit.com"]})
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "anyone@lekkacredit.com")
    client = TestClient(app)
    got = client.get("/api/journal_entries")
    assert got.status_code == 403 and got.json()["detail"] == "You don't have journal_entries:read"
    assert client.post("/api/forms/requisition/submissions/r/submit", json={"answers": {}}).status_code == 403
