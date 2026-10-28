"""What our own forms ask, and what they refuse: the UI draws them from these, and the API checks against them."""

import pytest
from pydantic import ValidationError

from forms import FORMS, VEHICLES
from requisition import Requisition

SIGNED = {"files": {"signed_requisition_form": ["gs://b/requisition/r/0a1b2c3d.pdf"]}}
LOAN = {
    "applicant_first_name": "Ada",
    "applicant_last_name": "Moyo",
    "loan_amount": 1500,
    "tenure": 6,
    "monthly_repayment": 290,
    "recommendation": "Approve",
}
TRIP = {"vehicle": VEHICLES[0], "date": "2026-10-27", "purpose": "Client visit, Chitungwiza"}


def test_every_question_has_a_title_of_its_own():
    for form in FORMS.values():
        for key, field in form.model.model_fields.items():
            assert field.title, (form.title, key)


@pytest.mark.parametrize("amount", [12.345, -1, 0])
def test_a_requisitions_amount_is_more_than_nothing_to_the_cent(amount):
    with pytest.raises(ValidationError):
        FORMS["requisition"].model(payable_to="Acme", amount=amount, **SIGNED)


def test_an_amount_to_the_cent_is_taken():
    assert FORMS["requisition"].model(payable_to="Acme", amount=1234.57, **SIGNED).amount == 1234.57


def test_a_requisition_as_stored_is_its_answers_and_who_sent_them():
    answers = FORMS["requisition"].model(payable_to="Acme", amount=60, **SIGNED).model_dump()
    identity = {"response_number": 1, "response_id": "r", "submitted_by": "a@x", "submitted_at": "2026-10-27T10:00Z"}
    assert Requisition(**answers, **identity).payable_to == "Acme"


def test_a_trip_goes_forwards():
    assert FORMS["vehicle_log"].model(**TRIP, odometer_start=100, odometer_end=100).odometer_end == 100
    with pytest.raises(ValidationError, match="Below the odometer at start"):
        FORMS["vehicle_log"].model(**TRIP, odometer_start=100, odometer_end=99)


def test_a_vehicle_is_one_of_ours():
    with pytest.raises(ValidationError):
        FORMS["vehicle_log"].model(**TRIP | {"vehicle": "A bicycle"}, odometer_start=0, odometer_end=1)


@pytest.mark.parametrize(
    "link, ok",
    [
        ("https://drive.google.com/drive/folders/1AbC_d-9", True),
        ("https://drive.google.com/drive/u/0/folders/1AbC", True),
        ("https://drive.google.com/file/d/1AbC/view", False),
        ("https://example.com/drive/folders/1AbC", False),
    ],
)
def test_a_client_folder_is_a_drive_folders_link(link, ok):
    names = LOAN
    if ok:
        assert FORMS["loan_approval"].model(**names, client_folder=link).client_folder == link
    else:
        with pytest.raises(ValidationError):
            FORMS["loan_approval"].model(**names, client_folder=link)


def test_a_choice_is_one_of_its_options():
    with pytest.raises(ValidationError):
        FORMS["loan_approval"].model(**LOAN | {"recommendation": "Maybe"})


def test_a_loan_says_how_much_for_how_long_at_what_a_month_and_what_you_recommend():
    with pytest.raises(ValidationError) as e:
        FORMS["loan_approval"].model(applicant_first_name="Ada", applicant_last_name="Moyo")
    assert {err["loc"][0] for err in e.value.errors()} == {
        "loan_amount",
        "tenure",
        "monthly_repayment",
        "recommendation",
    }


def test_how_the_ui_asks_is_in_the_schema():
    props = FORMS["write_off"].model.model_json_schema()["properties"]
    assert props["justification"]["anyOf"][0]["kind"] == "long"
    assert props["original_principal"]["anyOf"][0]["kind"] == "amount"
    assert props["supporting_documents"]["kind"] == "files"


def test_a_requisition_needs_its_signed_form():
    with pytest.raises(ValidationError, match="signed_requisition_form"):
        FORMS["requisition"].model(payable_to="Acme", amount=60, files={"receipts": ["gs://b/x.pdf"]})
