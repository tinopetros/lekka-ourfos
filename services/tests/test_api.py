"""ourfos-api: who's signed in, and Firestore's documents as the UI sees them, every shape they've had."""

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from google.auth import crypt, jwt

from api import auth, views
from api.main import app
from integrations import gcs

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
    "files": {"signed_requisition_form": ["signed-id"], "receipts": ["drive-id", "gs://bucket/x.pdf"]},
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
    me = TestClient(app).get("/api/me").json()
    assert (me["email"], me["environment"], me["version"]) == ("someone@lekkacredit.com", "local", "local")


def test_local_sign_in_is_refused_on_cloud_run(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("K_SERVICE", "ourfos-api")
    with pytest.raises(RuntimeError):
        auth.local()


def test_each_form_has_its_own_title(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    titles = {f["key"]: f["title"] for f in TestClient(app).get("/api/forms").json()}
    assert titles["loan_approval"] == "Loan approvals" and titles["write_off"] == "Write-offs"


def test_a_file_is_only_ever_ours(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", "ourfos-dev-attachments")
    client = TestClient(app)
    assert client.get("/api/files", params={"ref": "gs://someone-elses/x.pdf"}).status_code == 403
    assert client.get("/api/files", params={"ref": "https://example.com/x.pdf"}).status_code == 400


def test_a_file_streams_through_with_its_type(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", "ourfos-dev-attachments")

    class Response:
        ok, status_code, headers = True, 200, {"Content-Type": "application/pdf"}

        def iter_content(self, size):
            yield b"%PDF"

    asked = []
    monkeypatch.setattr(
        gcs, "session", lambda: type("S", (), {"get": lambda self, url, **kw: asked.append(url) or Response()})()
    )
    got = TestClient(app).get("/api/files", params={"ref": "gs://ourfos-dev-attachments/r/receipt one.pdf"})
    assert got.content == b"%PDF" and got.headers["content-type"] == "application/pdf"
    assert asked == ["https://storage.googleapis.com/storage/v1/b/ourfos-dev-attachments/o/r%2Freceipt%20one.pdf"]


def test_a_requisitions_row_and_answers():
    doc = {
        "answers": REQUISITION,
        "status": "done",
        "live_entry": "T1",
        "test": True,
        "received_at": "2026-10-01T10:00:01Z",
    }
    row = views.summary("requisition", "r", doc)
    assert row.response_number == 7 and row.received_at is not None
    assert (row.title, row.amount, row.live_entry, row.test, row.status) == ("Acme", 1234.5, "T1", True, "done")
    answers = views.answers("requisition", doc)
    assert [(a.label, a.text) for a in answers[:2]] == [("Payable to", "Acme"), ("Amount", "$1,234.50")]
    assert answers[2].label == "Signed requisition form"
    assert [(f.name, f.drive_id, f.ref) for f in answers[3].files] == [
        ("File 1", "drive-id", None),
        ("File 2", None, "gs://bucket/x.pdf"),
    ]


def test_a_text_forms_answers_are_in_its_order_with_links_and_empty_ones_left_out():
    answers = {"applicant_first_name": "Ada", "client_folder": "https://drive.google.com/x", "purpose": ""}
    rows = views.answers("loan_approval", {"answers": answers})
    assert [(a.label, a.text, a.link) for a in rows] == [
        ("Applicant First Name", "Ada", None),
        ("Link to Applicant Client Folder", None, "https://drive.google.com/x"),
    ]


def test_an_invalid_submission_shows_what_was_sent():
    doc = {"status": "handed_over", "run": "x", "raw": {"answers": "?"}}
    sheet = views.submission("vehicle_log", "v", doc, [], [])
    assert sheet.title is None and sheet.answers == [] and sheet.raw == {"answers": "?"}
    assert sheet.submitted_at is None and sheet.status == "handed_over"


def test_an_old_requisition_shape_still_shows_its_answers():
    rows = views.answers("requisition", {"answers": {"payable_to": "Acme", "an_old_field": "x"}})
    assert ("payable_to", "Acme") in [(a.label, a.text) for a in rows]


LINE = {"name": "Fuel", "glCode": "5040", "glId": 70, "amount": 60, "type": "DEBIT", "accountType": "EXPENSE"}


def test_a_runs_posted_lines_now_and_in_phase_11():
    assert views.run("a", {"workflow": "expense", "posted": {"lines": [LINE]}}).posted[0].name == "Fuel"
    assert views.run("b", {"workflow": "expense", "posted": [LINE]}).posted[0].name == "Fuel"


def test_a_correction_run():
    run = views.run(
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
    assert run.workflow == "correction"
    assert (run.entry, run.reversal, run.mifos_transaction_id, run.request.reason) == ("T1", "T2", "T3", "Fuel")
    assert [e.kind for e in run.emails] == ["correction"]


def test_an_intake_run_is_only_what_every_run_has():
    run = views.run("i", {"workflow": "intake", "status": "done", "emails": {"acknowledgement": {}}})
    assert run.workflow == "intake" and run.status == "done" and not hasattr(run, "classification")


def test_a_run_of_a_shape_we_dont_know_still_shows_how_it_ended():
    run = views.run("d", {"workflow": "expense", "status": "done", "classification": ["?"]})
    assert (run.workflow, run.status, run.classification) == ("expense", "done", None)


def test_a_workflow_we_dont_know_says_what_it_was():
    run = views.run("e", {"workflow": "approval", "status": "done"})
    assert (run.workflow, run.name, run.status) == ("unknown", "approval", "done")


def test_runs_newest_first_and_posting_off_says_so():
    later = views.run(
        "later", {"workflow": "expense", "execution": {"started_at": "2026-10-02T00:00:00Z"}, "mifos": False}
    )
    earlier = views.run("earlier", {"workflow": "expense", "execution": {"started_at": "2026-10-01T00:00:00Z"}})
    sheet = views.submission("requisition", "r", {"answers": REQUISITION}, [earlier, later], [])
    assert [r.id for r in sheet.runs] == ["later", "earlier"] and sheet.runs[0].skipped == "mifos"


def test_a_journal_entry():
    entry = views.journal_entry("T1", {"lines": [LINE], "status": "reversed", "reversed_by": "T2", "office": {"id": 1}})
    assert (entry.transaction_id, entry.reversed_by, entry.lines[0].glId) == ("T1", "T2", 70)


def test_unknown_forms_are_404(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    assert TestClient(app).get("/api/forms/nope/submissions").status_code == 404


def test_our_own_forms_answers_are_titled_as_it_asks():
    answers = {"source": "ourfos", "client_first_name": "Ada", "total_recovered": 20, "supporting_documents": ["d"]}
    rows = views.answers("write_off", {"answers": answers})
    assert [(a.label, a.text) for a in rows[:2]] == [("Client's first name", "Ada"), ("Total recovered", "$20.00")]
    assert rows[2].label == "Supporting documents" and rows[2].files[0].drive_id == "d"


def test_a_write_off_is_named_as_either_form_names_its_client():
    assert views.summary("write_off", "w", {"answers": {"client_full_name": "Ada Moyo"}}).title == "Ada Moyo"
    named = {"client_first_name": "Ada", "client_last_name": "Moyo"}
    assert views.summary("write_off", "w", {"answers": named}).title == "Ada Moyo"


def test_a_submissions_own_file_streams_by_its_short_path(monkeypatch):
    monkeypatch.setenv("AUTH", "local")
    monkeypatch.setenv("ACT_AS", "a@lekkacredit.com")
    monkeypatch.setenv("ATTACHMENTS_BUCKET", "ourfos-dev-attachments")

    class Response:
        ok, status_code, headers = True, 200, {"Content-Type": "image/png"}

        def iter_content(self, size):
            yield b"png"

    asked = []
    monkeypatch.setattr(
        gcs, "session", lambda: type("S", (), {"get": lambda self, url, **kw: asked.append(url) or Response()})()
    )
    client = TestClient(app)
    got = client.get("/api/files/vehicle_log/v1/989fb3b9.png")
    assert got.content == b"png" and asked[0].endswith("/o/vehicle_log%2Fv1%2F989fb3b9.png")
    assert client.get("/api/files/vehicle_log/v1/..%2Fx").status_code in (400, 404)
    assert client.get("/api/files/nope/v1/a.png").status_code == 404
