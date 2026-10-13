"""Correcting a posted requisition: its live entry's mirror, then the corrected lines, with the connector faked."""

import os

import pytest
from fastapi import HTTPException
from mifos_connector import MifosNetworkError

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

import httpx
from test_forms import Doc
from test_mifos import CREDIT, DEBIT, REQUISITION

import emails
import journal
import store
from common import execution_id
from integrations import mifos
from routers import corrections

NAMES = {66: ("5020", "Advertising and Promotions"), 109: ("10000000", "Cash at Vault"), 70: ("5040", "Fuel")}
FUEL = [{"name": "Fuel", "glCode": "5040", "glId": 70, "accountType": "EXPENSE", "amount": 60}]
LINES = {"debit": FUEL, "credit": CREDIT}


class Journal:
    """The connector's journal_entries: each post its own transaction, read back as Mifos would have it"""

    def __init__(self):
        self.created, self.fail = [], None

    def create(self, data):
        if self.fail:
            raise self.fail
        self.created.append(data)
        return {"officeId": 1, "transactionId": f"T{len(self.created)}"}

    def list_all(self, params):
        n = int(params["transactionId"][1:])
        data = self.created[n - 1]
        return [line(d["glAccountId"], "DEBIT", d["amount"], n) for d in data["debits"]] + [
            line(c["glAccountId"], "CREDIT", c["amount"], n) for c in data["credits"]
        ]


def line(gl, side, amount, n):
    return {
        "id": n * 10 + gl,
        "glAccountId": gl,
        "glAccountCode": NAMES[gl][0],
        "glAccountName": NAMES[gl][1],
        "entryType": {"value": side},
        "amount": amount,
        "transactionDate": [2026, 10, 5],
        "createdDate": [2026, 10, 6],
        "officeId": 1,
        "currency": {"code": "USD"},
    }


@pytest.fixture
def docs(monkeypatch):
    # Posted by run-0 as L1, as phase 11's post and read-back leave it
    docs = {
        ("requisition", "r"): {
            "answers": REQUISITION,
            "thread": {"thread_id": "t1"},
            "live_entry": "L1",
            "journal_entries": ["L1"],
        },
        ("journal_entries", "L1"): {
            "transaction_date": "2026-10-05",
            "reference_number": "REQ-7",
            "lines": [mifos.line(DEBIT[0], "DEBIT"), mifos.line(CREDIT[0], "CREDIT")],
            "status": "live",
        },
    }
    monkeypatch.setattr(store, "submission", lambda form, id: Doc(docs, (form, id)))
    monkeypatch.setattr(store, "run", lambda form, id, run: Doc(docs, (form, id, run)))
    monkeypatch.setattr(journal, "entry", lambda txn: Doc(docs, ("journal_entries", txn)))

    execution_id.set("run-1")
    return docs


@pytest.fixture
def mifos_journal(monkeypatch):
    fake = Journal()
    monkeypatch.setattr(mifos, "client", lambda: type("Client", (), {"journal_entries": fake})())
    return fake


@pytest.fixture
def sent(monkeypatch):
    sent = []

    def send(form, kind, submitter, sender, subject, html, text, thread=None, test=False):
        sent.append((kind, html, thread))
        return {"message_id": f"m{len(sent)}", "thread_id": "t1"}

    monkeypatch.setattr(corrections, "send", send)
    monkeypatch.setattr(emails, "form_name", lambda form: "Requisition Approval Request Form")
    return sent


ASK = {"reason": "Fuel, not advertising", "requested_by": "accountant@lekkacredit.com"}


def correct(lines=LINES):
    started = corrections.start("r", ASK | ({"lines": lines} if lines else {}))
    reversal = corrections.reverse("r", {})["mifos_transaction_id"]
    new = corrections.post("r", {}).get("mifos_transaction_id")
    corrections.confirm("r", {"thread": started["thread"]})
    return reversal, new


def test_a_correction_reverses_the_live_entry_on_its_date_then_posts_the_new_lines(docs, mifos_journal, sent):
    _, new = correct()
    mirror, corrected = mifos_journal.created
    assert mirror["debits"] == [{"glAccountId": 109, "amount": 60}]
    assert mirror["credits"] == [{"glAccountId": 66, "amount": 60}]
    assert mirror["transactionDate"] == corrected["transactionDate"] == "2026-10-05"
    assert mirror["referenceNumber"] == corrected["referenceNumber"] == "REQ-7"
    assert mirror["comments"].startswith(
        "Reversal of transaction L1. Reason: Fuel, not advertising. Requested by: accountant@lekkacredit.com. Subject: "
    )
    assert corrected["comments"].startswith("Correction of transaction L1. ")
    assert corrected["debits"] == [{"glAccountId": 70, "amount": 60}]

    requisition = docs[("requisition", "r")]
    assert requisition["live_entry"] == new == "T2"
    assert requisition["journal_entries"] == ["L1", "T1", "T2"]
    assert {"status": "reversed", "reversed_by": "T1"}.items() <= docs[("journal_entries", "L1")].items()
    assert docs[("journal_entries", "T1")]["reverses"] == "L1"
    assert docs[("journal_entries", "T1")]["by"] == docs[("journal_entries", "T2")]["by"] == ASK["requested_by"]
    assert docs[("journal_entries", "T2")]["status"] == "live"
    assert docs[("journal_entries", "T2")]["transaction_date"] == "2026-10-05"

    (kind, html, thread), *rest = sent
    assert kind == "correction" and not rest and thread == {"thread_id": "t1"}
    assert "Lekkai's action: CORRECTED" in html and "Mifos transaction ID: T2" in html and "Fuel" in html
    assert "Cash at Vault" in html and emails.DISCLAIMER not in html


def test_a_corrected_requisition_can_be_corrected_again(docs, mifos_journal, sent):
    correct()
    execution_id.set("run-2")
    docs[("requisition", "r", "run-1")]["status"] = "done"
    correct()
    assert docs[("requisition", "r")]["journal_entries"] == ["L1", "T1", "T2", "T3", "T4"]
    assert docs[("journal_entries", "T2")]["reversed_by"] == "T3"
    assert mifos_journal.created[2]["comments"].startswith("Reversal of transaction T2. ")


def test_no_lines_is_a_reversal_only(docs, mifos_journal, sent):
    _, new = correct(lines=None)
    assert new is None and len(mifos_journal.created) == 1
    assert docs[("requisition", "r")]["live_entry"] is None
    assert "Lekkai's action: REVERSED" in sent[0][1] and "L1 is reversed, nothing re-posted" in sent[0][1]


def test_a_retried_step_never_posts_twice(docs, mifos_journal, sent):
    corrections.start("r", ASK | {"lines": LINES})
    corrections.start("r", ASK | {"lines": LINES})
    assert corrections.reverse("r", {}) == corrections.reverse("r", {})
    assert corrections.post("r", {}) == corrections.post("r", {})
    assert len(mifos_journal.created) == 2


def test_a_mirror_that_may_have_landed_blocks_the_entry_until_mifos_is_checked(docs, mifos_journal, sent):
    corrections.start("r", ASK)
    mifos_journal.fail = MifosNetworkError("timed out", httpx.ReadTimeout("slow"))
    with pytest.raises(HTTPException) as e:
        corrections.reverse("r", {})
    assert e.value.status_code == 504
    assert docs[("journal_entries", "L1")]["reversing"] == "run-1"
    # Not even the same run tries again
    mifos_journal.fail = None
    with pytest.raises(HTTPException) as e:
        corrections.reverse("r", {})
    assert e.value.status_code == 409 and mifos_journal.created == []
    execution_id.set("run-2")
    with pytest.raises(HTTPException) as e:
        corrections.start("r", ASK)
    assert e.value.status_code == 409 and "Check Mifos" in e.value.detail


def test_a_mirror_that_certainly_didnt_land_blocks_nothing(docs, mifos_journal, sent):
    corrections.start("r", ASK)
    mifos_journal.fail = MifosNetworkError("refused", httpx.ConnectError("refused"))
    with pytest.raises(HTTPException) as e:
        corrections.reverse("r", {})
    assert e.value.status_code == 503
    assert docs[("journal_entries", "L1")]["reversing"] is None
    execution_id.set("run-2")
    assert corrections.start("r", ASK)["entry"] == "L1"


@pytest.mark.parametrize(
    "submission, original, given, says",
    [
        ({}, {}, None, "Nothing posted"),
        ({"live_entry": "L1"}, {}, "L0", "isn't this requisition's live entry"),
        ({"live_entry": "L1"}, {"reversing": "a"}, None, "Check Mifos"),
    ],
)
def test_a_correction_is_refused_when_theres_nothing_to_correct(docs, submission, original, given, says):
    docs[("requisition", "r")] = {"answers": REQUISITION} | submission
    docs[("journal_entries", "L1")] |= original
    with pytest.raises(HTTPException) as e:
        corrections.start("r", ASK | ({"transaction_id": given} if given else {}))
    assert e.value.status_code == 409 and says in e.value.detail


@pytest.mark.parametrize(
    "ask, says",
    [
        ({"reason": "x"}, "a reason and who asked"),
        (ASK | {"lines": {"debit": FUEL, "credit": []}}, "a debit and a credit"),
        (ASK | {"lines": {"debit": FUEL, "credit": [CREDIT[0] | {"amount": 50}]}}, "do not balance"),
        (ASK | {"lines": {"debit": [FUEL[0] | {"glId": "70"}], "credit": CREDIT}}, "glId a number"),
        (ASK | {"lines": {"debit": [FUEL[0] | {"amount": -60}], "credit": CREDIT}}, "more than 0"),
    ],
)
def test_corrected_lines_must_make_an_entry(docs, ask, says):
    with pytest.raises(HTTPException) as e:
        corrections.start("r", ask)
    assert e.value.status_code == 422 and says in e.value.detail


def test_a_refused_correction_leaves_no_status(docs):
    docs[("requisition", "r")]["live_entry"] = None
    with pytest.raises(HTTPException):
        corrections.start("r", ASK)
    assert "status" not in docs[("requisition", "r", "run-1")]
