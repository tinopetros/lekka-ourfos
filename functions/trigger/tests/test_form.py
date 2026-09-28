import json
from datetime import date, datetime
from pathlib import Path

import pytest

from form import HARARE, Invalid, clean, drive_ids

FORM = {
    "submitter_email_address": " LTanga@lekkacredit.com ",
    "comment": "",
    "date_disbursed": "Apr 10, 2026",
    "invoices": "",
    "signed_requisition_form": "<a href='https://drive.google.com/open?id=1SadMsMDjnTLSW-9JsqkQIKc4WYndlqwz'>File 1</a>",
    "total_amount": "1",
    "receipts": "",
    "payable_to": " City parking ",
    "form_id": "1FAIpQLSf-form",
    "form_name": "Requisition Approval Request Form",
    "response_number": "482",
    "response_date": "Apr 10, 2026, 3:45:12 PM",
    "response_id": "2_ABaOnud-response",
}

FIXTURES = Path(__file__).parents[3] / "workflows/fixtures"


def invalid(**changes) -> list[str]:
    with pytest.raises(Invalid) as e:
        clean(FORM | changes)
    return e.value.errors


def test_clean():
    r = clean(FORM)
    assert r.response_number == 482
    assert r.submitted_by == "ltanga@lekkacredit.com"
    assert r.payable_to == "City parking"
    assert r.amount == 1.0
    assert r.disbursed_on == date(2026, 4, 10)
    assert r.submitted_at == datetime(2026, 4, 10, 15, 45, 12, tzinfo=HARARE)
    assert r.comment is None
    assert r.files.signed_requisition_form == ["1SadMsMDjnTLSW-9JsqkQIKc4WYndlqwz"]
    assert r.files.receipts == []


def test_extra_keys_are_ignored():
    assert clean(FORM | {"something_new": "x"}).response_number == 482


def test_json_and_firestore():
    r = clean(FORM)
    assert r.to_json()["disbursed_on"] == "2026-04-10"
    assert r.to_json()["submitted_at"] == "2026-04-10T15:45:12+02:00"
    assert "comment" not in r.to_json()
    assert r.to_firestore()["disbursed_on"] == "2026-04-10"
    assert isinstance(r.to_firestore()["submitted_at"], datetime)


@pytest.mark.parametrize(
    "raw, want",
    [
        ("611.23", 611.23),
        ("$1,200.50", 1200.5),
        ("1,000,000", 1000000.0),
        ("USD 45", 45.0),
        (" 7 ", 7.0),
        (250, 250.0),
    ],
)
def test_amount(raw, want):
    assert clean(FORM | {"total_amount": raw}).amount == want


@pytest.mark.parametrize("raw", ["abc", "1.200,00", "12,00", "-5", "12..3"])
def test_amount_not_a_number(raw):
    assert invalid(total_amount=raw) == ["total_amount: not a number"]


def test_amount_zero():
    assert invalid(total_amount="0") == ["total_amount: input should be greater than 0"]


@pytest.mark.parametrize("raw", ["2026-04-10", "Apr 10, 2026", "April 10, 2026", "10 Apr 2026", "10 April 2026"])
def test_date(raw):
    assert clean(FORM | {"date_disbursed": raw}).disbursed_on == date(2026, 4, 10)


@pytest.mark.parametrize("raw", ["04/10/2026", "10/04/2026", "yesterday"])
def test_date_is_never_guessed(raw):
    assert invalid(date_disbursed=raw)[0].startswith("date_disbursed: not a date we can read without guessing")


@pytest.mark.parametrize(
    "raw, want",
    [
        ("2026-04-10T13:45:12Z", datetime(2026, 4, 10, 15, 45, 12, tzinfo=HARARE)),
        ("2026-04-10T15:45:12", datetime(2026, 4, 10, 15, 45, 12, tzinfo=HARARE)),
        ("1775828712000", datetime(2026, 4, 10, 15, 45, 12, tzinfo=HARARE)),
        ("Apr 10, 2026 15:45", datetime(2026, 4, 10, 15, 45, tzinfo=HARARE)),
    ],
)
def test_submitted_at(raw, want):
    assert clean(FORM | {"response_date": raw}).submitted_at == want


def test_required():
    assert invalid(response_number="", payable_to="  ", total_amount=None) == [
        "response_number: field required",
        "payable_to: field required",
        "total_amount: field required",
    ]


def test_every_problem_at_once():
    assert invalid(response_number="48a", submitter_email_address="nobody", total_amount="abc") == [
        "response_number: not a whole number",
        "submitter_email_address: not an email address",
        "total_amount: not a number",
    ]


def test_not_text():
    assert invalid(payable_to={"a": 1}) == ["payable_to: not text"]


@pytest.mark.parametrize(
    "raw, want",
    [
        ("", []),
        ("<a href='https://drive.google.com/open?id=A1'>File 1</a>", ["A1"]),
        (
            '<a href="https://drive.google.com/open?id=A1">File 1</a>, <a href="https://drive.google.com/open?id=B2">File 2</a>',
            ["A1", "B2"],
        ),
        (
            "<a href='https://drive.google.com/open?id=A1'>1</a><a href='https://drive.google.com/open?id=B2'>2</a>",
            ["A1", "B2"],
        ),
        ("https://drive.google.com/open?id=A1, https://drive.google.com/open?id=B2", ["A1", "B2"]),
        ("https://drive.google.com/file/d/A1/view?usp=sharing", ["A1"]),
        ("https://drive.google.com/uc?export=download&id=A1", ["A1"]),
        ("https://drive.google.com/open?id=A1 https://drive.google.com/open?id=A1", ["A1"]),
        ("File 1", []),
    ],
)
def test_drive_ids(raw, want):
    assert drive_ids(raw) == want


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_every_fixture_cleans(fixture):
    raw = json.loads(fixture.read_text())
    raw.pop("simulate", None)
    assert clean(raw).response_number == 482
