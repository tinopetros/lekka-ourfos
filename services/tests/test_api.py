"""ourfos-api: who's signed in, and Firestore's documents as the UI sees them, every shape they've had."""

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from google.auth import crypt, jwt

from api import auth, reads
from api.main import app

AUDIENCE = "/projects/1/locations/africa-south1/services/ourfos-api"


@pytest.fixture(autouse=True)
def unseen(monkeypatch):
    """A sign-in's record is written in a thread of its own, which could outlive a test's fake store: never here"""
    monkeypatch.setattr(auth, "seen", lambda email: None)


REQUISITION = {
    "response_number": 7,
    "response_id": "r",
    "submitted_by": "a@lekkacredit.com",
    "submitted_at": "2026-10-01T10:00:00Z",
    "payable_to": "Acme",
    "amount": 1234.5,
    "files": {"receipts": ["drive-id", "gs://bucket/x.pdf"]},
}


@pytest.fixture
def iap(monkeypatch):
    """IAP's key, as its certificates URL would serve it, and a way to sign as IAP does."""
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(auth, "certs", lambda refresh=False: {"k1": pem.decode()})
    signer = crypt.ES256Signer.from_string(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        "k1",
    )

    def sign(**claims):
        now = int(time.time())
        payload = {"iss": auth.ISSUER, "aud": AUDIENCE, "email": "Tino@lekkacredit.com", "iat": now, "exp": now + 600}
        return jwt.encode(signer, payload | claims).decode()

    monkeypatch.setenv("IAP_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("AUTH", raising=False)
    return sign


def test_iaps_header_says_who(iap):
    assert auth.verify(iap(), AUDIENCE) == "tino@lekkacredit.com"


@pytest.mark.parametrize(
    "claims", [{"aud": "/projects/1/locations/africa-south1/services/other"}, {"iss": "https://elsewhere"}]
)
def test_a_token_for_another_service_or_from_another_issuer_is_refused(iap, claims):
    with pytest.raises(ValueError):
        auth.verify(iap(**claims), AUDIENCE)


def test_every_route_needs_iaps_header(iap):
    client = TestClient(app)
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={auth.HEADER: "nonsense"}).status_code == 401
    me = client.get("/api/me", headers={auth.HEADER: iap()})
    assert me.status_code == 200 and me.json()["email"] == "tino@lekkacredit.com"


def test_a_sign_in_that_cant_be_recorded_is_still_a_sign_in():
    # conftest's store refuses: logged, not raised
    auth.record("tino@lekkacredit.com")


def test_locally_who_you_are_is_acted_as_or_your_adc(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "Someone@lekkacredit.com")
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert TestClient(app).get("/api/me").json() == {
        "email": "someone@lekkacredit.com",
        "environment": "local",
        "version": "local",
    }


def test_local_sign_in_is_refused_on_cloud_run(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("K_SERVICE", "ourfos-api")
    with pytest.raises(RuntimeError):
        auth.local()


def test_a_form_is_titled_by_its_noun():
    assert [reads.title(f) for f in ("requisition", "vehicle_log", "write_off")] == [
        "Requisitions",
        "Vehicle logs",
        "Write-off requests",
    ]


def test_a_requisitions_row_and_answers():
    doc = {"answers": REQUISITION, "status": "done", "live_entry": "T1", "test": True, "response_number": 7}
    row = reads.summary("requisition", "r", doc)
    assert (row.title, row.amount, row.live_entry, row.test, row.status) == ("Acme", 1234.5, "T1", True, "done")
    answers = reads.answers("requisition", doc)
    assert [(a.label, a.text) for a in answers[:2]] == [("Payable To", "Acme"), ("Total Amount", "$1,234.50")]
    assert [(f.name, f.url) for f in answers[2].files] == [
        ("File 1", "https://drive.google.com/open?id=drive-id"),
        ("File 2", None),
    ]


def test_a_text_forms_answers_are_in_its_order_with_links_and_empty_ones_left_out():
    answers = {"applicant_first_name": "Ada", "client_folder": "https://drive.google.com/x", "purpose": ""}
    rows = reads.answers("loan_approval", {"answers": answers})
    assert [(a.label, a.text, a.link) for a in rows] == [
        ("Applicant First Name", "Ada", None),
        ("Link to Applicant Client Folder", None, "https://drive.google.com/x"),
    ]


def test_an_invalid_submission_shows_what_was_sent():
    doc = {"status": "handed_over", "run": "x", "raw": {"answers": "?"}}
    sheet = reads.submission("vehicle_log", "v", doc, [], [])
    assert sheet.title is None and sheet.answers == [] and sheet.raw == {"answers": "?"}
    assert sheet.submitted_at is None and sheet.status == "handed_over"


def test_an_old_requisition_shape_still_shows_its_answers():
    rows = reads.answers("requisition", {"answers": {"payable_to": "Acme", "an_old_field": "x"}})
    assert ("payable_to", "Acme") in [(a.label, a.text) for a in rows]


LINE = {"name": "Fuel", "glCode": "5040", "glId": 70, "amount": 60, "type": "DEBIT", "accountType": "EXPENSE"}


def test_a_runs_posted_lines_now_and_in_phase_11():
    assert reads.run("a", {"posted": {"lines": [LINE]}}).posted[0].name == "Fuel"
    assert reads.run("b", {"posted": [LINE]}).posted[0].name == "Fuel"


def test_a_correction_run():
    run = reads.run(
        "c",
        {
            "workflow": "correction",
            "status": "done",
            "entry": "T1",
            "reversal": {"transaction_id": "T2"},
            "mifos_transaction_id": "T3",
            "request": {"reason": "Fuel", "requested_by": "x@lekkacredit.com", "debit": [LINE], "credit": []},
            "emails": {"correction": {"message_id": "m"}},
        },
    )
    assert (run.entry, run.reversal, run.mifos_transaction_id, run.request.reason) == ("T1", "T2", "T3", "Fuel")
    assert [e.kind for e in run.emails] == ["correction"]


def test_a_run_of_a_shape_we_dont_know_still_shows_how_it_ended():
    run = reads.run("d", {"workflow": "expense", "status": "done", "classification": ["?"]})
    assert (run.workflow, run.status, run.classification) == ("expense", "done", None)


def test_runs_newest_first_and_posting_off_says_so():
    later = reads.run("later", {"execution": {"started_at": "2026-10-02T00:00:00Z"}, "mifos": False})
    earlier = reads.run("earlier", {"execution": {"started_at": "2026-10-01T00:00:00Z"}})
    sheet = reads.submission("requisition", "r", {"answers": REQUISITION}, [earlier, later], [])
    assert [r.id for r in sheet.runs] == ["later", "earlier"] and sheet.runs[0].skipped == "mifos"


def test_a_journal_entry():
    entry = reads.journal_entry("T1", {"lines": [LINE], "status": "reversed", "reversed_by": "T2", "office": {"id": 1}})
    assert (entry.transaction_id, entry.reversed_by, entry.lines[0].glId) == ("T1", "T2", 70)


def test_unknown_forms_are_404(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    assert TestClient(app).get("/api/forms/nope/submissions").status_code == 404
