import base64
import email
import json
from email import policy
from pathlib import Path

import pytest

import emails
from forms import FORMS as SPECS
from integrations.workspace import gmail
from requisition import Requisition

REQUISITION = Requisition(
    response_number=843,
    response_id="r",
    submitted_by="tpetros@lekkacredit.com",
    submitted_at="2026-09-28T21:34:33Z",
    payable_to="Mr Muchenje",
    amount=60,
    disbursed_on="2026-09-18",
    comment="LMS Support fee for August 2026",
    files={"signed_requisition_form": ["A1"], "receipts": ["B2", "gs://ourfos-dev-attachments/r/receipts/0f"]},
)

CLASSIFICATION = {
    "approve": True,
    "reason": "Wellcash collection commission",
    "debit": [
        {
            "name": "Debtors collection commission - Lawyers",
            "glCode": "5077",
            "glId": 138,
            "accountType": "EXPENSE",
            "amount": 155.0,
        }
    ],
    "credit": [{"name": "Cash at Vault", "glCode": "10000000", "glId": 109, "accountType": "ASSET", "amount": 155.0}],
    "comments": ["Requisition has two approval signatures"],
}


R = "requisition"

FORMS = {
    "requisition": {
        "name": "Requisition Approval Request Form",
        "notify_to": ["lekkai@lekkacredit.com", " Directors@lekkacredit.com"],
    },
    "vehicle_log": {"name": "Vehicle Log Form", "notify_to": ["lekkai@lekkacredit.com"]},
    "loan_approval": {
        "name": "Loan Approval Request Form",
        "notify_to": ["lekkai@lekkacredit.com", "directors@lekkacredit.com"],
        "reply_to": ["directors@lekkacredit.com", "lekkai@lekkacredit.com"],
    },
    "write_off": {"name": "Write-off Request Form", "notify_to": ["lekkai@lekkacredit.com"]},
}

FIXTURES = Path(__file__).parents[2] / "workflows/fixtures"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("WORKSPACE_SUBJECT", "lekkai@lekkacredit.com")
    monkeypatch.setenv("FORMS", json.dumps(FORMS))
    monkeypatch.setenv("TEST_TO", "tpetros@lekkacredit.com")
    emails.config.cache_clear()


def test_subject_is_the_forms():
    assert emails.subject(R, "Mr Muchenje", 843) == "Requisition Approval Request Form - Mr Muchenje - #843"


def test_subject_keeps_whatever_parts_there_are():
    assert emails.subject(R, None, "12") == "Requisition Approval Request Form - #12"
    assert emails.subject(R) == "Requisition Approval Request Form"


def test_recipients_are_the_list_and_the_submitter_once_each():
    assert emails.recipients(R, "tpetros@lekkacredit.com") == (
        ["lekkai@lekkacredit.com", "directors@lekkacredit.com", "tpetros@lekkacredit.com"],
        0,
    )
    assert emails.recipients(R, "LEKKAI@lekkacredit.com")[0] == ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
    assert emails.recipients(R, None) == (["lekkai@lekkacredit.com", "directors@lekkacredit.com"], 0)


@pytest.mark.parametrize(
    "submitter", ["someone@gmail.com", "x@lekkacredit.com.evil.com", "x@evil.com@lekkacredit.com", "lekkacredit.com"]
)
def test_only_our_domain_is_mailed(submitter):
    assert emails.recipients(R, submitter) == (["lekkai@lekkacredit.com", "directors@lekkacredit.com"], 1)


@pytest.mark.parametrize("amount, want", [(60, "60"), (1234.5, "1,234.50"), (96.97, "96.97")])
def test_money(amount, want):
    assert emails.money(amount) == want


def test_an_acknowledgement_is_the_forms_answers():
    html, text = emails.acknowledgement(R, REQUISITION)
    assert "<strong>Requisition Approval Request Form has a new entry from tpetros@lekkacredit.com:</strong>" in html
    assert f"{emails.QUESTION}Date Disbursed</th>{emails.TD}Sep 18, 2026</td>" in html
    assert '<a href="https://drive.google.com/open?id=B2">File 1</a>, File 2' in html
    assert "Invoice(s)" not in html
    assert "Total Amount: $60" in text
    assert "Receipt(s): File 1 https://drive.google.com/open?id=B2, File 2" in text
    assert "Reference Number" not in text


def test_a_reference_number_is_shown_when_the_form_has_one():
    _, text = emails.acknowledgement(R, REQUISITION.model_copy(update={"reference_number": "REQ-0482"}))
    assert "Reference Number: REQ-0482" in text


def test_the_forms_values_are_escaped():
    html, _ = emails.acknowledgement(
        R, REQUISITION.model_copy(update={"payable_to": "<b>x</b>", "comment": "a & <script>"})
    )
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "a &amp; &lt;script&gt;" in html
    assert "<script>" not in html


def test_a_suggestion_is_ourfos_v2s_reply():
    html, text = emails.suggestion(CLASSIFICATION)
    assert html.startswith("<strong>Lekkai's suggestion: APPROVE</strong>")
    assert emails.TAKE_OVER not in html
    td = emails.TD
    assert f"{td}5077</td>{td}138</td>{td}EXPENSE</td>{td}155</td>{td}</td>" in html
    assert f"{td}Cash at Vault</td>{td}10000000</td>{td}109</td>{td}ASSET</td>{td}</td>{td}155</td>" in html
    assert "<li>Requisition has two approval signatures</li>" in html
    assert emails.DISCLAIMER in html and emails.DISCLAIMER in text


def test_a_rejection_is_deferred_to_an_accountant_without_a_table():
    html, text = emails.suggestion({"approve": False, "reason": "A salary", "debit": [], "credit": [], "comments": []})
    assert "Lekkai's suggestion: DEFER" in html
    assert "<table" not in html
    assert emails.TAKE_OVER in html and emails.TAKE_OVER in text


def test_a_handover_shows_what_the_form_sent_when_it_couldnt_be_read():
    html, text = emails.handover(R, "total_amount: not a number", {"total_amount": "sixty <dollars>"})
    assert html.startswith(
        "<strong>Lekkai failed to process this requisition: an accountant needs to take it from here.</strong>"
    )
    assert "total_amount: not a number" in html
    assert "sixty &lt;dollars&gt;" in html
    assert "total_amount: sixty <dollars>" in text


def parsed(m) -> email.message.EmailMessage:
    return email.message_from_bytes(m.as_bytes(), policy=policy.default)


def test_a_first_email_is_html_with_text_from_the_forms_name():
    m = parsed(
        gmail.message(
            ["a@lekkacredit.com", "b@lekkacredit.com"], "Requisition Approval Request Form", "s", "<p>hi</p>", "hi"
        )
    )
    assert m["From"] == "Requisition Approval Request Form <lekkai@lekkacredit.com>"
    assert m["To"] == "a@lekkacredit.com, b@lekkacredit.com"
    assert m["In-Reply-To"] is None
    assert [p.get_content_type() for p in m.iter_parts()] == ["text/plain", "text/html"]


def test_a_reply_points_at_the_first_email():
    m = parsed(gmail.message(["a@lekkacredit.com"], "Lekkai", "s", "<p>hi</p>", "hi", "<abc@mail.gmail.com>"))
    assert m["In-Reply-To"] == m["References"] == "<abc@mail.gmail.com>"


def test_a_subject_is_one_line_whatever_the_form_held():
    assert parsed(gmail.message(["a@lekkacredit.com"], "L", "a\r\nBcc: x@evil.com", "", ""))["Subject"] == (
        "a Bcc: x@evil.com"
    )


def test_a_reply_is_sent_in_its_thread(monkeypatch):
    sent = {}

    def call(scope, method, url, json):
        sent.update(scope=scope, body=json)
        return type("R", (), {"json": lambda self: {"id": "m2", "threadId": "t1"}})()

    monkeypatch.setattr(gmail, "call", call)
    got = gmail.send(["a@lekkacredit.com"], "Lekkai", "s", "<p>hi</p>", "hi", {"thread_id": "t1", "in_reply_to": "<x>"})
    assert got == {"message_id": "m2", "thread_id": "t1"}
    assert sent["scope"] == gmail.GMAIL_SEND
    assert sent["body"]["threadId"] == "t1"
    assert b"In-Reply-To: <x>" in base64.urlsafe_b64decode(sent["body"]["raw"])


def test_a_test_tells_lekkai_and_a_submitter_test_to_lists():
    assert emails.recipients(R, " TPetros@lekkacredit.com", test=True) == (
        ["lekkai@lekkacredit.com", "tpetros@lekkacredit.com"],
        0,
    )


@pytest.mark.parametrize("submitter", ["ltanga@lekkacredit.com", "someone@gmail.com", None])
def test_a_test_tells_only_lekkai_otherwise(submitter):
    assert emails.recipients(R, submitter, test=True) == (["lekkai@lekkacredit.com"], 0)


def test_a_tests_subject_says_so():
    assert (
        emails.subject(R, "Mr Muchenje", -482, test=True)
        == "[TEST] Requisition Approval Request Form - Mr Muchenje - #-482"
    )


IDENTITY = {
    "response_number": -482,
    "response_id": "r",
    "submitted_by": "lekkai@lekkacredit.com",
    "submitted_at": "2026-04-10T13:45:12Z",
}


def submission(form: str, **changes):
    """A form's happy fixture, as the trigger cleans it: text, empty answers dropped, uploads as Drive ids."""
    raw = json.loads((FIXTURES / form / "happy.json").read_text())
    spec = SPECS[form]
    answers = {k: raw[k] for k in spec.labels if raw.get(k) and k not in spec.files}
    answers |= {k: ["1x1lpayZJdJ17d1vXw9fnFTtmOej43s2g"] for k in spec.files if raw.get(k)}
    return spec.model(**IDENTITY, **answers | changes)


def test_every_new_forms_acknowledgement_is_its_answers_in_its_order():
    html, text = emails.acknowledgement("vehicle_log", submission("vehicle_log"))
    assert "<strong>Vehicle Log Form has a new entry from lekkai@lekkacredit.com:</strong>" in html
    labels = [line.split(":")[0] for line in text.splitlines()[2:]]
    assert labels[:4] == ["Email address", "Trip Name / Purpose", "Destination", "Vehicle"]
    assert labels[-1] == "Vehicle Images"
    assert "Issues Description" not in labels
    assert '<a href="https://drive.google.com/open?id=1x1lpayZJdJ17d1vXw9fnFTtmOej43s2g">File 1</a>' in html


def test_a_loan_reads_as_the_add_ons_did():
    """#613's order: the case, then the recommendation, and the folder last."""
    _, text = emails.acknowledgement("loan_approval", submission("loan_approval"))
    labels = [line.split(":")[0] for line in text.splitlines()[2:]]
    assert labels[:4] == [
        "Email address",
        "Applicant First Name",
        "Applicant Last Name",
        "Character - What's your assessment of the client's character?",
    ]
    assert labels[-3:] == [
        'What is your personal recommendation e.g. "Approve/Disapprove"',
        "Overall assessment (anything else that you would you like the approvers to know?)",
        "Link to Applicant Client Folder",
    ]


def test_a_lone_link_is_linked_and_a_line_break_kept():
    html, _ = emails.acknowledgement(
        "loan_approval",
        submission("loan_approval", purpose="Stock\n<b>and</b> fuel", client_folder="https://x/y?a=1&b"),
    )
    assert f'{emails.TD}<a href="https://x/y?a=1&amp;b">https://x/y?a=1&amp;b</a></td>' in html
    assert f"{emails.TD}Stock<br>&lt;b&gt;and&lt;/b&gt; fuel</td>" in html


@pytest.mark.parametrize(
    "form, answers, want",
    [
        ("requisition", {"payable_to": "Mr Muchenje"}, "Requisition Approval Request Form - Mr Muchenje - #-482"),
        ("vehicle_log", {"trip_name_purpose": "CBD"}, "Vehicle Log Form - CBD - #-482"),
        (
            "loan_approval",
            {"applicant_first_name": "Fixture", "applicant_last_name": "Applicant"},
            "Loan Approval Request Form - Fixture Applicant - #-482",
        ),
        ("write_off", {"client_full_name": "Fixture Client"}, "Write-off Request Form - Fixture Client - #-482"),
        ("loan_approval", {"applicant_last_name": "Applicant"}, "Loan Approval Request Form - Applicant - #-482"),
    ],
)
def test_every_forms_subject_is_its_add_ons(form, answers, want):
    assert emails.subject(form, emails.names(form, answers), -482) == want


@pytest.mark.parametrize(
    "form, want",
    [
        ("requisition", "requisition: an accountant"),
        ("vehicle_log", "vehicle log: someone"),
        ("loan_approval", "loan approval request: a director"),
        ("write_off", "write-off request: a director"),
    ],
)
def test_a_handover_says_what_it_was_and_who_takes_it(form, want):
    html, _ = emails.handover(form, "POST /acknowledge: 500")
    assert html.startswith(f"<strong>Lekkai failed to process this {want} needs to take it from here.</strong>")


def test_every_forms_list_is_its_own():
    assert emails.recipients("vehicle_log", "tpetros@lekkacredit.com")[0] == [
        "lekkai@lekkacredit.com",
        "tpetros@lekkacredit.com",
    ]


def test_a_loan_requests_replies_go_to_the_directors_and_lekkai():
    assert emails.reply_to("loan_approval") == ["directors@lekkacredit.com", "lekkai@lekkacredit.com"]
    assert emails.reply_to("loan_approval", test=True) == ["lekkai@lekkacredit.com"]
    assert emails.reply_to("vehicle_log") == emails.reply_to("vehicle_log", test=True) == []


def test_reply_to_is_a_header_only_when_there_is_one():
    assert parsed(gmail.message(["a@lekkacredit.com"], "L", "s", "", "", reply_to=["d@lekkacredit.com"]))[
        "Reply-To"
    ] == ("d@lekkacredit.com")
    assert parsed(gmail.message(["a@lekkacredit.com"], "L", "s", "", ""))["Reply-To"] is None
