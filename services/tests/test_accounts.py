"""The accounts a correction can post to: Mifos's postable ones, kept in Firestore and read again behind the answer once
a day old, the saved ones standing when Mifos fails."""

import base64
import json
import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from mifos_connector import MifosNetworkError

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

import store
from integrations import mifos
from main import app
from tests.firestore import Db


def account(id, code, name, usage="DETAIL", disabled=False, manual=True):
    return {
        "id": id,
        "glCode": code,
        "name": name,
        "type": {"id": 1, "code": "x", "value": "ASSET"},
        "usage": {"id": 1, "code": "x", "value": usage},
        "disabled": disabled,
        "manualEntriesAllowed": manual,
    }


CHART = [
    account(109, "10000000", "Cash at Vault"),
    account(1, "1000", "Assets", usage="HEADER"),
    account(2, "1001", "Old till", disabled=True),
    account(3, "1002", "Loan portfolio", manual=False),
    account(200, "1500", "Prepaid rent"),
]


class Accounts:
    def __init__(self):
        self.reads, self.fail = [], False

    def list(self, params):
        self.reads.append(params)
        if self.fail:
            raise MifosNetworkError("down")
        return CHART


@pytest.fixture
def chart(monkeypatch):
    accounts = Accounts()
    monkeypatch.setattr(mifos, "client", lambda tenant=None: type("Client", (), {"gl_accounts": accounts})())
    db = Db()
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setenv("MIFOS_TENANT_ID", "default")
    return accounts


class Now:
    """A thread that runs as it starts, so a refresh behind an answer is done by the next line"""

    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def behind(monkeypatch):
    monkeypatch.setattr(mifos.threading, "Thread", Now)


def age(tenant, days):
    ref = store.client().collection("mifos_accounts").document(tenant)
    ref.set(ref.get().to_dict() | {"read_at": datetime.now(UTC) - timedelta(days=days)})


def test_only_postable_accounts_by_code(chart):
    assert [(a["glId"], a["glCode"]) for a in mifos.accounts("demo")] == [(109, "10000000"), (200, "1500")]


def test_saved_accounts_answer_and_survive_a_restart(chart):
    mifos.accounts("demo")
    assert store.client().collection("mifos_accounts").document("demo").get().to_dict()["tenant"] == "demo"
    # An instance's memory is no part of it: what's saved answers
    mifos.accounts("demo")
    assert len(chart.reads) == 1


def test_a_day_old_answers_then_is_read_again_behind_it(chart, behind):
    first = mifos.accounts("demo")
    age("demo", 1)
    assert mifos.accounts("demo") == first
    assert len(chart.reads) == 2
    # Fresh again
    mifos.accounts("demo")
    assert len(chart.reads) == 2


def test_mifos_down_leaves_the_saved_ones_standing(chart, behind):
    first = mifos.accounts("demo")
    age("demo", 2)
    chart.fail = True
    assert mifos.accounts("demo") == first
    assert not mifos._refreshing
    # Each tenant its own: nothing read yet for this one, so there's nothing to answer with
    with pytest.raises(HTTPException):
        mifos.accounts("default")


def test_one_refresh_at_a_time(chart, monkeypatch):
    started = []
    monkeypatch.setattr(
        mifos.threading,
        "Thread",
        lambda target, args, daemon: type("T", (), {"start": lambda self: started.append(args)})(),
    )
    mifos.accounts("demo")
    age("demo", 1)
    mifos.accounts("demo")
    mifos.accounts("demo")
    assert started == [("demo",)]
    mifos._refreshing.clear()


def test_the_route_marks_expenser_s_and_only_serves_ours(chart):
    got = TestClient(app).get("/mifos/accounts", params={"tenant": "demo"})
    assert {a["glId"]: a["expenser"] for a in got.json()} == {109: True, 200: False}
    assert TestClient(app).get("/mifos/accounts", params={"tenant": "other"}).status_code == 422
    # Unasked, this environment's own
    TestClient(app).get("/mifos/accounts")
    assert store.client().collection("mifos_accounts").document("default").get().exists


def token(email):
    """An ID token as Cloud Run passes it on: checked, and its signature replaced"""
    header, claims = (
        base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
        for x in ({"alg": "RS256", "typ": "JWT"}, {"email": email})
    )
    return {"Authorization": f"Bearer {header}.{claims}.SIGNATURE_REMOVED_BY_GOOGLE"}


def test_ourfos_api_reads_accounts_and_nothing_else(chart, monkeypatch):
    monkeypatch.setenv("API_ACCOUNT", "ourfos-api@p.iam.gserviceaccount.com")
    client = TestClient(app)
    api = token("ourfos-api@p.iam.gserviceaccount.com")
    assert client.get("/mifos/accounts", params={"tenant": "demo"}, headers=api).status_code == 200
    assert client.post("/forms/requisition/r1/correction/post", json={}, headers=api).status_code == 403
    # The workflow, as ever, past the check: what its route then says is its own
    workflow = token("ourfos-workflow@p.iam.gserviceaccount.com")
    assert client.post("/forms/requisition/r1/correction/post", json={}, headers=workflow).status_code != 403
