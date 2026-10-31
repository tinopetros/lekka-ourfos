"""The mifos sync: paging Mifos gently, the first snapshot, latest and the change log. Mifos and the bucket faked."""

import json

import pytest
from fastapi import HTTPException

import mifos_sync
from integrations import mifos, mifos_bucket


def loan(id, status="Active", repaid=0, overdue=0, officer="Tendai"):
    return {
        "id": id,
        "status": {"value": status},
        "loanOfficerName": officer,
        "summary": {"totalRepayment": repaid, "totalOverdue": overdue, "principalOverdue": overdue},
        "inArrears": overdue > 0,
    }


class Listing:
    def __init__(self, world):
        self.world = world

    def list(self, params):
        self.world["asked"].append(params)
        start = params["offset"]
        return {"pageItems": self.world["mifos"][start : start + params["limit"]], "totalFilteredRecords": 1}


class Client:
    def __init__(self, world):
        self.loans = self.clients = Listing(world)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


@pytest.fixture
def world(monkeypatch):
    world = {"mifos": [], "asked": [], "bucket": {}, "timeouts": []}
    monkeypatch.setenv("MIFOS_BUCKET", "ourfos-prod-mifos")
    monkeypatch.setattr(mifos_sync, "PAGE", 2)
    world["clock"] = iter([])

    class Time:
        sleep = staticmethod(lambda s: world.setdefault("slept", []).append(s))
        monotonic = staticmethod(lambda: next(world["clock"], 0))

    monkeypatch.setattr(mifos_sync, "time", Time)
    monkeypatch.setattr(mifos, "connection", lambda timeout: world["timeouts"].append(timeout) or Client(world))
    monkeypatch.setattr(mifos_bucket, "read", lambda name: world["bucket"].get(name))
    monkeypatch.setattr(mifos_bucket, "write", lambda name, text: world["bucket"].__setitem__(name, text))
    monkeypatch.setattr(
        mifos_bucket,
        "append",
        lambda name, text: world["bucket"].__setitem__(name, world["bucket"].get(name, "") + text),
    )
    monkeypatch.setattr(
        mifos_bucket, "names", lambda prefix: sorted(n for n in world["bucket"] if n.startswith(prefix))
    )
    return world


def lines(world, name):
    return [json.loads(x) for x in world["bucket"].get(name, "").splitlines()]


def test_the_first_night_keeps_a_first_snapshot_and_latest(world):
    world["mifos"] = [loan(1), loan(2), loan(3)]
    result = mifos_sync.run("loans")
    first = [n for n in world["bucket"] if n.startswith("loans/dt=")]
    assert len(first) == 1 and first[0].endswith("/part-0001.jsonl")
    assert world["bucket"][first[0]] == world["bucket"]["loans/latest/part-0001.jsonl"]
    assert [x["id"] for x in lines(world, "loans/latest/part-0001.jsonl")] == [1, 2, 3]
    assert result | {"at": None, "seconds": None, "pages": None, "read_seconds": None, "bytes": None} == {
        "at": None,
        "kind": "loans",
        "rows": 3,
        "pages": None,
        "read_seconds": None,
        "seconds": None,
        "bytes": None,
        "first": True,
        "new": 0,
        "changed": 0,
        "gone": 0,
    }
    assert "loans/_changes.jsonl" not in world["bucket"]
    assert lines(world, "loans/_perf.jsonl")[0]["rows"] == 3


def test_pages_until_a_short_page_never_by_mifos_total_and_pauses_between(world):
    world["mifos"] = [loan(1), loan(2), loan(3), loan(4)]
    mifos_sync.run("loans")
    assert [p["offset"] for p in world["asked"]] == [0, 2, 4]
    assert all(p["orderBy"] == "id" and p["sortOrder"] == "ASC" for p in world["asked"])
    assert world["slept"] == [mifos_sync.PAUSE, mifos_sync.PAUSE]
    assert world["timeouts"] == [mifos_sync.SLOW + 5]


def test_a_later_night_logs_new_changed_and_gone_and_replaces_latest(world):
    world["mifos"] = [loan(1), loan(2, repaid=50), loan(3)]
    mifos_sync.run("loans")
    first = next(n for n in world["bucket"] if n.startswith("loans/dt="))
    world["mifos"] = [loan(1), loan(2, repaid=100, status="Closed (obligations met)"), loan(4)]
    result = mifos_sync.run("loans")
    assert (result["new"], result["changed"], result["gone"]) == (1, 1, 1)
    changes = {c["id"]: c for c in lines(world, "loans/_changes.jsonl")}
    assert changes[4]["change"] == "new"
    # One gone keeps its last whole record, as the night before had it
    assert changes[3]["change"] == "gone"
    assert {k: v for k, v in changes[3]["last"].items() if k != "_fetched_at"} == loan(3)
    assert changes[2]["fields"] == {
        "status.value": ["Active", "Closed (obligations met)"],
        "summary.totalRepayment": [50, 100],
    }
    assert [x["id"] for x in lines(world, "loans/latest/part-0001.jsonl")] == [1, 2, 4]
    # The first snapshot is never rewritten
    assert [x["id"] for x in lines(world, first)] == [1, 2, 3]


def test_what_the_calendar_moves_is_not_a_change(world):
    world["mifos"] = [loan(1)]
    mifos_sync.run("loans")
    world["mifos"] = [loan(1, overdue=30)]
    assert mifos_sync.run("loans")["changed"] == 0
    assert lines(world, "loans/latest/part-0001.jsonl")[0]["summary"]["totalOverdue"] == 30


def test_a_slow_page_stops_and_writes_only_its_perf_line(world):
    world["mifos"] = [loan(1), loan(2), loan(3)]
    mifos_sync.run("loans")
    before = dict(world["bucket"])
    world["mifos"] = [loan(1), loan(2), loan(3, repaid=10)]
    # The night starts, the first page starts, and answers 61s later
    world["clock"] = iter([0, 0, 61])
    with pytest.raises(HTTPException) as e:
        mifos_sync.run("loans")
    assert e.value.status_code == 503
    assert world["bucket"]["loans/latest/part-0001.jsonl"] == before["loans/latest/part-0001.jsonl"]
    assert "loans/_changes.jsonl" not in world["bucket"]
    assert "took 61" in lines(world, "loans/_perf.jsonl")[-1]["error"]


def test_refused_where_there_is_no_mifos_bucket(world, monkeypatch):
    monkeypatch.delenv("MIFOS_BUCKET")
    with pytest.raises(HTTPException) as e:
        mifos_sync.run("loans")
    assert e.value.status_code == 409
    assert world["asked"] == []


def test_only_clients_and_loans(world):
    with pytest.raises(HTTPException) as e:
        mifos_sync.run("journal_entries")
    assert e.value.status_code == 404
