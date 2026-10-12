"""Mifos's manual entries into our record: paging back to the mark, and the preload. Mifos and the store faked."""

import pytest
from test_forms import Doc

import sync
from integrations import mifos

OURS = "lekkai@lekkacredit.com"


def raw(id, txn, by="ZSaruchera", gl=66, side="DEBIT"):
    return {
        "id": id,
        "transactionId": txn,
        "createdByUserName": by,
        "glAccountId": gl,
        "glAccountCode": "5020",
        "glAccountName": "Advertising and Promotions",
        "entryType": {"value": side},
        "amount": 10,
        "transactionDate": [2026, 1, 5],
        "createdDate": [2026, 10, 6],
        "officeId": 1,
        "currency": {"code": "USD"},
    }


# Newest first: two lines a transaction
MIFOS = [
    raw(1302, "P4", side="CREDIT"),
    raw(1301, "P4"),
    raw(1202, "L3", OURS, side="CREDIT"),
    raw(1201, "L3", OURS),
    raw(1102, "P2", side="CREDIT"),
    raw(1101, "P2"),
    raw(702, "P1", side="CREDIT"),
    raw(701, "P1"),
]


@pytest.fixture
def world(monkeypatch):
    world = {"docs": {}, "pages": [], "read": [], "written": {}, "mark": None, "held": set()}
    monkeypatch.setenv("MIFOS_USERNAME", OURS)
    monkeypatch.setattr(sync, "PAGE", 3)

    def manual_entries(params):
        world["pages"].append(params)
        rows = sorted(MIFOS, key=lambda x: x["id"], reverse=params["sortOrder"] == "DESC")
        return rows[params["offset"] : params["offset"] + params["limit"]]

    def read(txn):
        world["read"].append(txn)
        return mifos.entry(txn, [x for x in MIFOS if x["transactionId"] == txn])

    def raise_mark(highest, added):
        world["mark"] = max(world["mark"] or 0, highest)

    monkeypatch.setattr(mifos, "manual_entries", manual_entries)
    monkeypatch.setattr(mifos, "read", read)
    monkeypatch.setattr(sync, "mark", lambda: Doc(world["docs"], ("syncs", "journal_entries")))
    monkeypatch.setattr(sync, "held", lambda txns: set(txns) & world["held"])
    monkeypatch.setattr(sync, "raise_mark", raise_mark)
    monkeypatch.setattr(sync, "posted_by_runs", lambda: {"L3": ("requisition", "r", "run-1")})
    monkeypatch.setattr(sync, "write", lambda found, runs: world["written"].update(found) or len(found))
    return world


def test_with_no_mark_nothing_is_read(world):
    assert sync.journal_entries() == {"skipped": "not preloaded"}
    assert world["pages"] == [] and world["mark"] is None


def test_each_night_pages_back_past_the_mark_and_adds_only_peoples_new_entries(world):
    world["docs"][("syncs", "journal_entries")] = {"last_entry_id": 1105}
    world["held"] = {"P2"}
    assert sync.journal_entries() == {"added": 1, "last_entry_id": 1302, "was": 1105}
    # 10 under the mark is 1095: P2 again, which we hold, and L3, which is ours. Never P1
    assert sorted(world["written"]) == ["P4"] and world["read"] == ["P4"]
    assert all(p["sortOrder"] == "DESC" for p in world["pages"]) and len(world["pages"]) == 3
    assert world["mark"] == 1302
    assert [x["type"] for x in world["written"]["P4"]["lines"]] == ["CREDIT", "DEBIT"]


def test_the_preload_takes_everything_since_its_date_ours_too(world):
    assert sync.journal_entries("2026-01-01") == {"added": 4, "transactions": 4, "last_entry_id": 1302}
    assert world["pages"][0]["fromDate"] == "2026-01-01" and world["pages"][0]["sortOrder"] == "ASC"
    # A page ends halfway through P2, and its lines are still one entry
    assert len(world["written"]["P2"]["lines"]) == 2 and world["read"] == []
    assert world["mark"] == 1302


def test_a_preloaded_entry_is_lekkais_with_its_run_when_a_run_posted_it(monkeypatch):
    monkeypatch.setenv("MIFOS_USERNAME", OURS)
    runs = {"L3": ("requisition", "r", "run-1")}
    assert sync.recorded("L3", {"created_by": OURS}, runs) | {"recorded_at": None} == {
        "created_by": OURS,
        "source": "lekkai",
        "form": "requisition",
        "submission": "r",
        "run": "run-1",
        "status": "live",
        "recorded_at": None,
    }
    assert sync.recorded("L9", {"created_by": OURS}, runs)["source"] == "lekkai"
    assert sync.recorded("P1", {"created_by": "ZSaruchera"}, runs)["source"] == "mifos"
