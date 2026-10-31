"""A requisition's live entry undone or corrected from the UI: the correction workflow, with no lines or with them."""

import pytest
from fastapi.testclient import TestClient

import store
from api.main import app
from integrations import services, workflows
from tests.firestore import Db

URL = "/api/forms/requisition/submissions/r1/reverse"
CORRECT = "/api/forms/requisition/submissions/r1/correct"
ACCOUNTS = [
    {"glId": 109, "glCode": "10000000", "name": "Cash at Vault", "type": "ASSET", "expenser": True},
    {"glId": 66, "glCode": "5020", "name": "Advertising and Promotions", "type": "EXPENSE", "expenser": True},
    {"glId": 200, "glCode": "1500", "name": "Prepaid rent", "type": "ASSET", "expenser": False},
]
ADA = "ada@lekkacredit.com"


class Runs(list):
    asked: list


@pytest.fixture
def started(monkeypatch, groups_of):
    db = Db()
    db.docs[("requisitions", "r1")] = {"live_entry": "T1", "answers": {}}
    db.docs[("journal_entries", "T1")] = {"tenant": "demo"}
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", ADA)
    groups_of[ADA] = {"directors@lekkacredit.com"}
    runs = Runs()
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: runs.append((workflow, argument)) or "e1")
    asked = []
    monkeypatch.setattr(services, "get", lambda path, params: asked.append((path, params)) or ACCOUNTS)
    runs.asked = asked
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


def lines(debit, credit):
    return {
        "debit": [{"glId": g, "amount": a} for g, a in debit],
        "credit": [{"glId": g, "amount": a} for g, a in credit],
    }


def test_an_entry_without_a_tenant_leaves_it_to_the_services(started):
    store.client().docs[("journal_entries", "T1")] = {}
    body = {"transaction_id": "T1", "reason": "Advertising", "lines": lines([(66, 40), (200, 20)], [(109, 60)])}
    assert TestClient(app).post(CORRECT, json=body).status_code == 200
    # Theirs is where the workflow posts an entry like it: no guess here
    assert started.asked == [("/mifos/accounts", {})]


def test_a_correction_starts_one_with_mifos_s_own_accounts(started):
    body = {"transaction_id": "T1", "reason": "Advertising", "lines": lines([(66, 40), (200, 20)], [(109, 60)])}
    got = TestClient(app).post(CORRECT, json=body)
    assert got.status_code == 200 and got.json() == {"run": "e1"}
    # The entry's tenant's accounts, and their names and codes as Mifos has them, whatever the page sent
    assert started.asked == [("/mifos/accounts", {"tenant": "demo"})]
    ((workflow, argument),) = started
    assert workflow == "correction" and argument["lines"] == {
        "debit": [
            {"name": "Advertising and Promotions", "glCode": "5020", "glId": 66, "amount": 40},
            {"name": "Prepaid rent", "glCode": "1500", "glId": 200, "amount": 20},
        ],
        "credit": [{"name": "Cash at Vault", "glCode": "10000000", "glId": 109, "amount": 60}],
    }


@pytest.mark.parametrize(
    "body",
    [
        {"lines": lines([(66, 50)], [(109, 60)])},
        {"lines": lines([(999, 60)], [(109, 60)])},
        {"lines": lines([(66, 0)], [(109, 0)])},
        {"lines": lines([], [(109, 60)])},
        {"lines": lines([(66, 60)], [(109, 60)]), "reason": " "},
    ],
    ids=["unbalanced", "unknown account", "nothing", "one side", "no reason"],
)
def test_a_correction_that_doesnt_add_up_starts_nothing(started, body):
    got = TestClient(app).post(CORRECT, json={"transaction_id": "T1", "reason": "x", **body})
    assert got.status_code == 422 and started == []


def test_only_the_live_entry_is_corrected(started):
    body = {"transaction_id": "T0", "reason": "x", "lines": lines([(66, 60)], [(109, 60)])}
    assert TestClient(app).post(CORRECT, json=body).status_code in (409, 422) and started == []


def test_accounts_put_expenser_s_first(started):
    got = TestClient(app).get("/api/accounts", params={"tenant": "demo"})
    assert [a["glId"] for a in got.json()] == [109, 66, 200]


def test_only_who_may_edit_reads_accounts_or_corrects(started, groups_of):
    groups_of[ADA] = set()
    assert TestClient(app).get("/api/accounts", params={"tenant": "demo"}).status_code == 403
    body = {"transaction_id": "T1", "reason": "x", "lines": lines([(66, 60)], [(109, 60)])}
    assert TestClient(app).post(CORRECT, json=body).status_code == 403 and started == []
