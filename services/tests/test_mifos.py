"""Posting to Mifos, its failures and its read-back, with the connector faked; and the steps around it."""

import os
from datetime import date, datetime

import httpx
import pytest
from fastapi import HTTPException
from mifos_connector import MifosApiError, MifosNetworkError

# routers.requisitions imports expenser, which reads it
os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from test_forms import Doc

import emails
import journal as journal_entries
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
        "id": 900 + gl,
        "transactionId": "L42",
        "createdDate": [2026, 10, 6],
        "createdByUserName": "lekkai@lekkacredit.com",
        "referenceNumber": "7",
        "comments": "Subject: s",
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


def test_a_simulated_post_never_reaches_mifos_and_is_its_own_each_time(journal):
    first = mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject", "stub")["mifos_transaction_id"]
    second = mifos.post("run-1", DEBIT, CREDIT, date(2026, 10, 5), "Subject", "stub")["mifos_transaction_id"]
    assert first.startswith(mifos.STUB) and first != second
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


@pytest.fixture
def docs(monkeypatch):
    docs = {("requisition", "r"): {"answers": REQUISITION}}
    monkeypatch.setattr(store, "submission", lambda form, id: Doc(docs, (form, id)))
    monkeypatch.setattr(store, "run", lambda form, id, run: Doc(docs, (form, id, run)))
    monkeypatch.setattr(journal_entries, "entry", lambda txn: Doc(docs, ("journal_entries", txn)))
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
        "Subject: Requisition Approval Request Form - City parking - #7. Response number: 7. Workflow run: run-1"
    )


def test_a_post_is_recorded_as_lekkais_and_live(docs, journal, sent):
    requisitions.post("r", {})
    recorded = docs[("journal_entries", "L42")]
    assert {k: recorded[k] for k in ("source", "by", "form", "submission", "run", "status", "transaction_date")} == {
        "source": "ourfos",
        "by": "lekkai",
        "form": "requisition",
        "submission": "r",
        "run": "run-1",
        "status": "live",
        "transaction_date": "2026-10-05",
    }
    assert [(x["type"], x["glId"]) for x in recorded["lines"]] == [("DEBIT", 66), ("CREDIT", 109)]
    assert docs[("requisition", "r")]["live_entry"] == "L42"
    assert docs[("requisition", "r")]["journal_entries"] == ["L42"]
    # What we sent, and the day we posted it: Mifos isn't read back
    assert recorded["created_on"] == datetime.now(journal_entries.HARARE).date().isoformat()
    assert docs[("requisition", "r", "run-1")]["posted"]["lines"] == recorded["lines"]


def test_a_post_is_referenced_by_the_requisitions_own_number_when_it_has_one(docs, journal, sent):
    docs[("requisition", "r")]["answers"] = REQUISITION | {"reference_number": "REQ-0482"}
    requisitions.post("r", {})
    assert journal.created[0]["referenceNumber"] == "REQ-0482"
    assert "REQ-0482" not in journal.created[0]["comments"]


@pytest.mark.parametrize("field, value, skipped", [("test", True, "test"), ("mifos", False, "mifos")])
def test_a_test_run_or_mifos_off_never_posts(docs, journal, field, value, skipped):
    docs[("requisition", "r", "run-1")][field] = value
    assert requisitions.post("r", {}) == {"skipped": skipped}
    assert journal.created == []


def test_the_last_email_is_what_we_posted_and_its_id(docs, journal, sent):
    requisitions.post("r", {})
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


class Office:
    """The connector's transport, for the one read a start makes: our office"""

    def __init__(self, fail=None):
        self.fail, self.asked = fail, []

    def get(self, path):
        self.asked.append(path)
        if self.fail:
            raise self.fail
        return {"id": 1, "name": "Head Office"}


def test_a_start_reads_our_office_and_logs_whether_mifos_answers(monkeypatch, capsys):
    monkeypatch.setenv("MIFOS_TENANT_ID", "demo")
    office = Office()
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"_http": office})())
    mifos.connect()
    assert office.asked == ["/offices/1"]
    failing = Office(fail=MifosNetworkError("refused", httpx.ConnectError("refused")))
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"_http": failing})())
    mifos.connect()
    out = capsys.readouterr().out
    assert '"mifos connected"' in out and "mifos not connected" in out
