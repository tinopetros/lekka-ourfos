"""Post journal entry: a requisition with nothing live posted from the UI, filed as Lekkai would have, through the
correction workflow with nothing to reverse."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_corrections import LINES, Journal, docs, sent  # noqa: F401  docs and sent are fixtures
from test_mifos import REQUISITION, Connection
from test_reverse import ACCOUNTS, ADA, lines

import store
from api import views
from api.main import app
from integrations import mifos, services, workflows
from routers import corrections
from tests.firestore import Db

URL = "/api/forms/requisition/submissions/r1/post"
FILED = {
    "reference": "REQ-7",
    "transaction_date": "2026-10-05",
    "comments": "Subject: City parking. Response number: 7.",
}
BODY = {**FILED, "lines": lines([(66, 60)], [(109, 60)])}


@pytest.fixture
def api(monkeypatch, groups_of):
    db = Db()
    db.docs[("requisitions", "r1")] = {"status": "handed_over", "answers": {}}
    monkeypatch.setattr(store, "client", lambda: db)
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", ADA)
    groups_of[ADA] = {"directors@lekkacredit.com"}
    started, asked = [], []
    monkeypatch.setattr(workflows, "start", lambda workflow, argument: started.append((workflow, argument)) or "e1")
    monkeypatch.setattr(services, "get", lambda path, params: asked.append(params) or ACCOUNTS)
    return db, started, asked


def test_a_handed_over_requisition_is_posted_through_the_correction_workflow(api):
    _, started, asked = api
    got = TestClient(app).post(URL, json=BODY | {"reference": " REQ-7 "})
    assert got.status_code == 200 and got.json() == {"run": "e1"}
    [(workflow, argument)] = started
    assert workflow == "correction" and "reason" not in argument and "transaction_id" not in argument
    assert argument["requested_by"] == ADA and argument["post"] == FILED
    assert argument["lines"]["debit"] == [
        {"name": "Advertising and Promotions", "glCode": "5020", "glId": 66, "amount": 60}
    ]
    # Not a test, so the environment's own tenant, as the services decide
    assert asked == [{}]


def test_a_test_ones_accounts_are_demos(api):
    db, _, asked = api
    db.docs[("requisitions", "r1")]["test"] = True
    TestClient(app).post(URL, json=BODY)
    assert asked == [{"tenant": "demo"}]


@pytest.mark.parametrize(
    ("doc", "status"),
    [({"live_entry": "T1"}, 409), ({"status": "closed"}, 409), ({"status": "disapproved"}, 409)],
    ids=["live", "closed", "closed on dev"],
)
def test_one_with_something_live_or_closed_isnt_posted(api, doc, status):
    db, started, _ = api
    db.docs[("requisitions", "r1")] |= doc
    assert TestClient(app).post(URL, json=BODY).status_code == status and not started


@pytest.mark.parametrize(
    "change",
    [{"reference": " "}, {"comments": ""}, {"lines": lines([(66, 50)], [(109, 60)])}, {"transaction_date": "5 Oct"}],
    ids=["no reference", "no comments", "unbalanced", "not a date"],
)
def test_a_post_that_isnt_filed_or_doesnt_add_up_starts_nothing(api, change):
    _, started, _ = api
    assert TestClient(app).post(URL, json=BODY | change).status_code == 422 and not started


def test_only_who_may_edit_entries_posts(api, groups_of):
    _, started, _ = api
    groups_of[ADA] = set()
    assert TestClient(app).post(URL, json=BODY).status_code == 403 and not started


def test_the_dialog_starts_as_lekkai_would_have_posted_it(monkeypatch):
    monkeypatch.setattr(views.emails, "form_name", lambda form: "Requisition Approval Request Form")
    doc = {"status": "handed_over", "answers": REQUISITION | {"reference_number": "REQ-7"}}
    posting = views.posting("requisition", doc)
    assert posting.reference == "REQ-7" and posting.transaction_date.isoformat() == "2026-10-05"
    assert posting.comments == "Subject: Requisition Approval Request Form - City parking - #7. Response number: 7."
    assert posting.tenant is None
    assert views.posting("requisition", doc | {"test": True}).tenant == "demo"


def test_without_a_reference_its_response_number_and_without_a_date_none():
    doc = {"status": "handed_over", "answers": {k: v for k, v in REQUISITION.items() if k != "disbursed_on"}}
    posting = views.posting("requisition", doc)
    assert posting.reference == "7" and posting.transaction_date is None


@pytest.mark.parametrize(
    ("form", "doc"),
    [
        ("requisition", {"live_entry": "T1"}),
        ("requisition", {"status": "closed"}),
        ("requisition", {"status": "draft"}),
        ("loan_approval", {"status": "done"}),
    ],
)
def test_nothing_to_post_where_something_is_live_its_closed_or_not_a_requisition(form, doc):
    assert views.posting(form, doc | {"answers": REQUISITION}) is None


@pytest.fixture
def unposted(docs):  # noqa: F811
    docs[("requisition", "r")] |= {"live_entry": None, "journal_entries": ["L1", "T0"], "status": "reversed"}
    return docs


@pytest.fixture
def journal(monkeypatch):
    monkeypatch.setenv("MIFOS_TENANT_ID", "default")
    fake = Journal()
    tenants = []
    monkeypatch.setattr(mifos, "connection", lambda tenant=None: tenants.append(tenant) or Connection(fake))
    fake.tenants = tenants
    return fake


ASK = {"requested_by": "accountant@lekkacredit.com", "lines": LINES, "post": FILED}


def test_the_workflow_posts_it_as_filed_with_the_run_and_nothing_reversed(unposted, journal, sent):  # noqa: F811
    started = corrections.start("r", ASK)
    assert started["entry"] is None and started["has_lines"]
    assert corrections.post("r", {})["mifos_transaction_id"] == "T1"
    [posted] = journal.created
    assert posted["referenceNumber"] == "REQ-7" and posted["transactionDate"] == "2026-10-05"
    assert posted["comments"] == "Subject: City parking. Response number: 7. Workflow run: run-1"
    assert posted["debits"] == [{"glAccountId": 70, "amount": 60}]
    requisition = unposted[("requisition", "r")]
    assert requisition["live_entry"] == "T1" and requisition["journal_entries"] == ["L1", "T0", "T1"]
    assert unposted[("journal_entries", "T1")]["by"] == "accountant@lekkacredit.com"

    corrections.confirm("r", {"thread": started["thread"]})
    [(kind, html, thread)] = sent
    assert kind == "correction" and thread == {"thread_id": "t1"}
    assert "accountant@lekkacredit.com posted the journal entry" in html and "REQ-7" in html and "Fuel" in html


def test_a_tests_post_goes_to_demo(unposted, journal, sent):  # noqa: F811
    unposted[("requisition", "r")]["test"] = True
    corrections.start("r", ASK)
    corrections.post("r", {})
    assert journal.tenants == ["demo"]


def test_a_retried_post_never_posts_twice(unposted, journal, sent):  # noqa: F811
    corrections.start("r", ASK)
    corrections.post("r", {})
    corrections.post("r", {})
    assert len(journal.created) == 1


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"lines": None}, 422),
        ({"post": FILED | {"reference": " "}}, 422),
        ({"post": FILED | {"transaction_date": "Oct 5"}}, 422),
        ({"requested_by": ""}, 422),
    ],
)
def test_a_post_needs_lines_where_to_file_them_and_who(unposted, change, says):
    with pytest.raises(HTTPException) as e:
        corrections.start("r", ASK | change)
    assert e.value.status_code == says


def test_a_post_is_refused_where_something_is_live(docs):  # noqa: F811
    with pytest.raises(HTTPException) as e:
        corrections.start("r", ASK)
    assert e.value.status_code == 409 and "L1" in e.value.detail


def test_a_correction_still_needs_its_reason(docs):  # noqa: F811
    with pytest.raises(HTTPException) as e:
        corrections.start("r", {"requested_by": "a@lekkacredit.com", "lines": LINES})
    assert e.value.status_code == 422
