import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from form import Invalid, clean, drive_ids

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
    "response_date": "Apr 10, 2026 3:45 PM",
    "created_at": "1775828712000",
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
    assert r.submitted_at == datetime(2026, 4, 10, 13, 45, 12, tzinfo=UTC)
    assert r.comment is None
    assert r.files.signed_requisition_form == ["1SadMsMDjnTLSW-9JsqkQIKc4WYndlqwz"]
    assert r.files.receipts == []


def test_extra_keys_are_ignored():
    assert clean(FORM | {"something_new": "x"}).response_number == 482


def test_json_and_firestore():
    r = clean(FORM)
    assert r.to_json()["disbursed_on"] == "2026-04-10"
    assert r.to_json()["submitted_at"] == "2026-04-10T13:45:12Z"
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


def test_submitted_at_is_created_at_not_response_date():
    # The real payload: created_at is 5:34 PM in New York, and response_date is in whatever zone the form is set to
    r = clean(FORM | {"created_at": "1790631273038", "response_date": "Sep 28, 2026 5:34 PM"})
    assert r.submitted_at == datetime(2026, 9, 28, 21, 34, 33, 38000, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["2026-04-10T13:45:12Z", "Sep 28, 2026 5:34 PM", "179063127303", "17906312730380"])
def test_created_at_is_epoch_milliseconds_only(raw):
    assert invalid(created_at=raw)[0].startswith("created_at: not epoch milliseconds")


def test_created_at_is_required():
    raw = dict(FORM)
    del raw["created_at"]
    with pytest.raises(Invalid) as e:
        clean(raw)
    assert e.value.errors == ["created_at: field required"]


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
