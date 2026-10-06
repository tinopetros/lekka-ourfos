"""Posting to Mifos, its failures and its read-back, with the connector faked; and the steps around it."""

import os
from datetime import date

import httpx
import pytest
from fastapi import HTTPException
from mifos_connector import MifosApiError, MifosNetworkError

# routers.requisitions imports expenser, which reads it
os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from test_forms import Doc

import emails
import store
from common import execution_id
from integrations import mifos
from routers import requisitions

DEBIT = [{"name": "Advertising and Promotions", "glCode": "5020", "glId": 66, "accountType": "EXPENSE", "amount": 60}]
CREDIT = [{"name": "Cash at Vault", "glCode": "10000000", "glId": 109, "accountType": "ASSET", "amount": 60}]
REQUISITION = {
    "response_number": 7,
    "response_id": "r",
    "submitted_by": "lekkai@lekkacredit.com",
    "submitted_at": "2026-04-10T13:45:12Z",
    "payable_to": "City parking",
    "amount": 60,
    "disbursed_on": "2026-10-05",
}


class Journal:
    """The connector's journal_entries, as Mifos would answer"""

    def __init__(self, fail=None):
        self.fail, self.created = fail, []

    def create(self, data):
        if self.fail:
            raise self.fail
        self.created.append(data)
        return {"officeId": 1, "transactionId": "L42"}

    def list(self, params):
        if self.fail:
            raise self.fail
        return {"totalFilteredRecords": 0, "pageItems": []}

    def list_all(self, params):
        return [entry(d["glAccountId"], "DEBIT", d["amount"]) for d in self.created[-1]["debits"]] + [
            entry(c["glAccountId"], "CREDIT", c["amount"]) for c in self.created[-1]["credits"]
        ]


def entry(gl, side, amount):
    names = {66: ("5020", "Advertising and Promotions"), 109: ("10000000", "Cash at Vault")}
    return {
        "glAccountId": gl,
        "glAccountCode": names[gl][0],
        "glAccountName": names[gl][1],
        "entryType": {"value": side},
        "amount": amount,
        "transactionDate": [2026, 10, 5],
        "officeId": 1,
        "officeName": "Head Office",
        "currency": {"code": "USD", "displaySymbol": "$"},
    }


@pytest.fixture
def journal(monkeypatch):
    journal = Journal()
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"journal_entries": journal})())
    monkeypatch.setenv("MIFOS_OFFICE_ID", "1")
    monkeypatch.setenv("MIFOS_CURRENCY", "USD")
    return journal


def test_a_post_is_a_journal_entry_with_our_reference(journal):
    assert mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject") == {"mifos_transaction_id": "L42"}
    assert journal.created == [
        {
            "officeId": 1,
            "currencyCode": "USD",
            "transactionDate": "2026-10-05",
            "dateFormat": "yyyy-MM-dd",
            "locale": "en",
            "referenceNumber": "run-1",
            "comments": "Subject",
            "debits": [{"glAccountId": 66, "amount": 60}],
            "credits": [{"glAccountId": 109, "amount": 60}],
        }
    ]


def test_a_simulated_post_never_reaches_mifos(journal):
    assert mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject", "stub") == {
        "mifos_transaction_id": "stub-txn-run-1"
    }
    assert journal.created == []


@pytest.mark.parametrize(
    "error, status",
    [
        (MifosApiError(400, {"defaultUserMessage": "GL account is closed"}), 422),
        (MifosNetworkError("refused", httpx.ConnectError("refused")), 503),
        (MifosNetworkError("timed out", httpx.ReadTimeout("slow")), 504),
        (MifosApiError(500, {"defaultUserMessage": "boom"}), 504),
    ],
)
def test_only_what_certainly_didnt_land_says_so(journal, error, status):
    journal.fail = error
    with pytest.raises(HTTPException) as e:
        mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject")
    assert e.value.status_code == status


def test_the_books_are_only_prods(monkeypatch):
    mifos.client.cache_clear()
    monkeypatch.setenv("MIFOS_TENANT_ID", "default")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "ourfos-dev")
    with pytest.raises(HTTPException) as e:
        mifos.client()
    assert "ourfos-prod" in e.value.detail


def test_a_read_back_is_what_mifos_has(journal):
    mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject")
    entry = mifos.read_back("L42", DEBIT, CREDIT)
    assert entry["mismatch"] is None
    assert {k: v for k, v in entry["posted"].items() if k != "lines"} == {
        "transaction_id": "L42",
        "date": "2026-10-05",
        "office": {"id": 1, "name": "Head Office"},
        "currency": "USD",
    }
    assert [(x["name"], x["type"], x["amount"]) for x in entry["posted"]["lines"]] == [
        ("Advertising and Promotions", "DEBIT", 60),
        ("Cash at Vault", "CREDIT", 60),
    ]


def test_verify_compares_each_line_not_the_count():
    wanted = [mifos.line(DEBIT[0], "DEBIT"), mifos.line(CREDIT[0], "CREDIT")]
    swapped = [mifos.line(DEBIT[0], "CREDIT"), mifos.line(CREDIT[0], "DEBIT")]
    assert mifos.mismatch(wanted, swapped) == (
        "missing debit 60.00 to GL 66, credit 60.00 to GL 109; not ours credit 60.00 to GL 66, debit 60.00 to GL 109"
    )
    assert mifos.mismatch(wanted, wanted[:1]) == "missing credit 60.00 to GL 109"
    assert mifos.mismatch(wanted, [{**wanted[0], "amount": 60.001}, wanted[1]]) is None


@pytest.fixture
def docs(monkeypatch):
    docs = {("requisition", "r"): {"answers": REQUISITION}}
    monkeypatch.setattr(store, "submission", lambda form, id: Doc(docs, (form, id)))
    monkeypatch.setattr(store, "run", lambda form, id, run: Doc(docs, (form, id, run)))
    execution_id.set("run-1")
    docs[("requisition", "r", "run-1")] = {"classification": {"approve": True, "debit": DEBIT, "credit": CREDIT}}
    return docs


@pytest.fixture
def sent(monkeypatch):
    sent = []

    def send(form, kind, submitter, sender, subject, html, text, thread=None, test=False):
        sent.append((kind, html))
        return {"message_id": f"m{len(sent)}", "thread_id": "t1"}

    monkeypatch.setattr(requisitions, "send", send)
    monkeypatch.setattr(emails, "form_name", lambda form: "Requisition Approval Request Form")
    return sent


def test_a_post_is_dated_the_day_it_was_disbursed_and_never_made_twice(docs, journal, sent):
    assert requisitions.post("r", {}) == {"mifos_transaction_id": "L42"}
    assert requisitions.post("r", {}) == {"mifos_transaction_id": "L42"}
    assert len(journal.created) == 1
    assert journal.created[0]["transactionDate"] == "2026-10-05"
    assert journal.created[0]["referenceNumber"] == "7"
    assert journal.created[0]["comments"] == (
        "Reference number: 7. Requisition Approval Request Form - City parking - #7. Response number: 7. "
        "Workflow run: run-1"
    )


def test_a_post_is_referenced_by_the_requisitions_own_number_when_it_has_one(docs, journal, sent):
    docs[("requisition", "r")]["answers"] = REQUISITION | {"reference_number": "REQ-0482"}
    requisitions.post("r", {})
    assert journal.created[0]["referenceNumber"] == "REQ-0482"
    assert journal.created[0]["comments"].startswith("Reference number: REQ-0482. ")


def test_a_test_run_never_posts(docs, journal, sent):
    docs[("requisition", "r", "run-1")]["test"] = True
    assert requisitions.post("r", {}) == {"skipped": "test"}
    assert journal.created == []
    requisitions.confirm("r", {"mifos_transaction_id": None, "thread": {"thread_id": "t1"}})
    assert "Lekkai's action: NOT POSTED" in sent[0][1] and emails.DISCLAIMER in sent[0][1]


def test_the_last_email_is_what_mifos_has_and_its_id(docs, journal, sent):
    requisitions.post("r", {})
    requisitions.read_back("r", "L42", None)
    requisitions.confirm("r", {"mifos_transaction_id": "L42", "thread": {"thread_id": "t1"}})
    requisitions.confirm("r", {"mifos_transaction_id": "L42", "thread": {"thread_id": "t1"}})
    assert [kind for kind, _ in sent] == ["confirmation"]
    html = sent[0][1]
    assert "Lekkai's action: POSTED" in html and "Mifos transaction ID: L42" in html
    assert "Cash at Vault" in html and emails.DISCLAIMER in html


def test_a_ledger_totals_each_side():
    _, text = emails.ledger([mifos.line(DEBIT[0], "DEBIT"), mifos.line(CREDIT[0], "CREDIT")])
    assert text == [
        "Account | GL Code | Debit | Credit",
        "Advertising and Promotions | 5020 | 60 | ",
        "Cash at Vault | 10000000 |  | 60",
        "Total |  | 60 | 60",
    ]


def test_a_start_logs_whether_mifos_answers(monkeypatch, capsys):
    monkeypatch.setenv("MIFOS_TENANT_ID", "demo")
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"journal_entries": Journal()})())
    mifos.connect()
    journal = Journal(fail=MifosNetworkError("refused", httpx.ConnectError("refused")))
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"journal_entries": journal})())
    mifos.connect()
    out = capsys.readouterr().out
    assert '"mifos connected"' in out and "mifos not connected" in out
