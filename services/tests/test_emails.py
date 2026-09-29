import base64
import email
from email import policy

import pytest

import emails
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


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("WORKSPACE_SUBJECT", "lekkai@lekkacredit.com")
    monkeypatch.setenv("FORM_NAME", "Requisition Approval Request Form")
    monkeypatch.setenv("NOTIFY_TO", "lekkai@lekkacredit.com, Directors@lekkacredit.com")


def test_subject_is_the_forms():
    assert emails.subject("Mr Muchenje", 843) == "Requisition Approval Request Form - Mr Muchenje - #843"


def test_subject_keeps_whatever_parts_there_are():
    assert emails.subject(None, "12") == "Requisition Approval Request Form - #12"
    assert emails.subject() == "Requisition Approval Request Form"


def test_recipients_are_the_list_and_the_submitter_once_each():
    assert emails.recipients("tpetros@lekkacredit.com") == (
        ["lekkai@lekkacredit.com", "directors@lekkacredit.com", "tpetros@lekkacredit.com"],
        0,
    )
    assert emails.recipients("LEKKAI@lekkacredit.com")[0] == ["lekkai@lekkacredit.com", "directors@lekkacredit.com"]
    assert emails.recipients(None) == (["lekkai@lekkacredit.com", "directors@lekkacredit.com"], 0)


@pytest.mark.parametrize(
    "submitter", ["someone@gmail.com", "x@lekkacredit.com.evil.com", "x@evil.com@lekkacredit.com", "lekkacredit.com"]
)
def test_only_our_domain_is_mailed(submitter):
    assert emails.recipients(submitter) == (["lekkai@lekkacredit.com", "directors@lekkacredit.com"], 1)


@pytest.mark.parametrize("amount, want", [(60, "60"), (1234.5, "1,234.50"), (96.97, "96.97")])
def test_money(amount, want):
    assert emails.money(amount) == want


def test_an_acknowledgement_is_the_forms_answers():
    html, text = emails.acknowledgement(REQUISITION)
    assert "<strong>Requisition Approval Request Form has a new entry from tpetros@lekkacredit.com:</strong>" in html
    assert f"{emails.TH}Date Disbursed</th>{emails.TD}Sep 18, 2026</td>" in html
    assert '<a href="https://drive.google.com/open?id=B2">File 1</a>, File 2' in html
    assert "Invoice(s)" not in html
    assert "Total Amount: 60" in text
    assert "Receipt(s): File 1 https://drive.google.com/open?id=B2, File 2" in text


def test_the_forms_values_are_escaped():
    html, _ = emails.acknowledgement(
        REQUISITION.model_copy(update={"payable_to": "<b>x</b>", "comment": "a & <script>"})
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
    html, text = emails.handover("total_amount: not a number", {"total_amount": "sixty <dollars>"})
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
