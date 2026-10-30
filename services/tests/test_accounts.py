"""The accounts a correction can post to: Mifos's postable ones, kept a while, and the last read when Mifos fails."""

import base64
import json
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from mifos_connector import MifosNetworkError

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from integrations import mifos
from main import app


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
    monkeypatch.setattr(mifos, "_accounts", {})
    monkeypatch.setenv("MIFOS_TENANT_ID", "default")
    return accounts


def test_only_postable_accounts_by_code(chart):
    assert [(a["glId"], a["glCode"]) for a in mifos.accounts("demo")] == [(109, "10000000"), (200, "1500")]


def test_a_read_is_kept_then_read_again(chart, monkeypatch):
    mifos.accounts("demo")
    mifos.accounts("demo")
    assert len(chart.reads) == 1
    monkeypatch.setattr(mifos, "ACCOUNTS_FOR", 0)
    mifos.accounts("demo")
    assert len(chart.reads) == 2


def test_mifos_down_falls_back_to_the_last_read(chart, monkeypatch):
    first = mifos.accounts("demo")
    monkeypatch.setattr(mifos, "ACCOUNTS_FOR", 0)
    chart.fail = True
    assert mifos.accounts("demo") == first
    # Each tenant its own: nothing read yet for this one
    with pytest.raises(HTTPException):
        mifos.accounts("default")


def test_the_route_marks_expenser_s_and_only_serves_ours(chart):
    got = TestClient(app).get("/mifos/accounts", params={"tenant": "demo"})
    assert {a["glId"]: a["expenser"] for a in got.json()} == {109: True, 200: False}
    assert TestClient(app).get("/mifos/accounts", params={"tenant": "other"}).status_code == 422


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
