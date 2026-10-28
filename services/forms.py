"""Every form we take: where it's stored, which workflow runs it, what it asks, and what its emails call it.

Each form's model is what our own form asks, strict: the UI draws the form from it, and the API checks what's sent
against it. Until a form's Google Form closes, the trigger takes it too, through what that Google Form sent: the
requisition's own model, the others' answers as text, strict only where the subject needs them. Their keys are the
webhook's own, and their labels the Google Form's questions, which old submissions are still shown by. Copied into
the trigger's zip, so it only imports pydantic.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, create_model, field_validator

from requisition import Requisition, RequisitionForm
from submission import AccountNumber, Amount, DriveFolder, FileRefs, LongText, Months, Submission


@dataclass(frozen=True)
class GoogleForm:
    """What a form's Google Form sent, until it closes: the trigger's model, and the labels its submissions are
    shown by."""

    model: type[Submission]
    # Text forms only: key to question, in the form's order
    labels: dict[str, str] = field(default_factory=dict)
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class Form:
    collection: str
    workflow: str
    model: type[BaseModel]
    google_form: GoogleForm
    # What the UI's lists and sidebar call it
    title: str
    # What a handover calls it, and who takes it from there
    noun: str
    taker: str
    # The answers the subject names, after the form's name, joined by a space: whichever a submission has, ours or
    # its Google Form's
    subject: tuple[str, ...]
    # What ours stores: what the form asks, and who sent it when
    submission: type[Submission] | None = None
    # Only a form whose status ourfos tracks shows it. The others show they were received: the rest is in their
    # email threads
    tracks_status: bool = False

    def __post_init__(self):
        if self.submission is None:
            ours = create_model(self.model.__name__.removesuffix("Form"), __base__=(self.model, Submission))
            object.__setattr__(self, "submission", ours)

    def stored(self, source: str | None) -> type[Submission]:
        """The model a stored submission reads as: ours, or what its Google Form sent."""
        return self.submission if source == "ourfos" else self.google_form.model


def text_form(name: str, labels: dict[str, str], required: tuple[str, ...], files: tuple[str, ...] = ()):
    """Every answer text, or a list of Drive ids for an upload. Only what the subject needs is required."""
    fields = {}
    for key in labels:
        if key in files:
            fields[key] = (list[str], [])
        elif key in required:
            fields[key] = (str, Field(min_length=1))
        else:
            fields[key] = (str | None, None)
    return create_model(name, __base__=Submission, **fields)


# The Google Form's list
VEHICLES = ("White Nissan Note | AGO8747",)


# A day's trip: who drove is who's signed in, and the distance is worked out
class VehicleLogForm(BaseModel):
    model_config = ConfigDict(extra="forbid", title="Vehicle log")

    vehicle: Literal[VEHICLES] = Field(title="Vehicle")
    # The form starts it at today
    date: dt.date = Field(title="Date", json_schema_extra={"prefill": "today"})
    purpose: str = Field(min_length=1, title="Purpose", description="Where to, and why")
    odometer_start: int = Field(ge=0, title="Odometer at start")
    odometer_end: int = Field(ge=0, title="Odometer at end")
    odometer_photos: FileRefs = Field([], title="Odometer photos")
    vehicle_photos: FileRefs = Field(
        [], title="Vehicle photos", description="Of anything worth a record: damage, a warning light"
    )
    comment: LongText | None = Field(
        None,
        title="Comment",
        description=(
            "Anything else: refuelling, fuel readings, repairs or checks, issues with the vehicle, other drivers, a "
            "trip over more than a day. Fuel and repairs that cost money go in a requisition"
        ),
    )

    # On the end's own field, so the form shows it there
    @field_validator("odometer_end")
    @classmethod
    def forwards(cls, end: int, info: ValidationInfo) -> int:
        start = info.data.get("odometer_start")
        if start is not None and end < start:
            raise ValueError("Below the odometer at start")
        return end


class LoanApprovalForm(BaseModel):
    model_config = ConfigDict(extra="forbid", title="Loan approval")

    applicant_first_name: str = Field(min_length=1, title="Applicant's first name")
    applicant_last_name: str = Field(min_length=1, title="Applicant's last name")
    applicant_other_names: str | None = Field(None, title="Applicant's other names")
    character: LongText | None = Field(
        None, title="Character", description="What's your assessment of the client's character?"
    )
    purpose: LongText | None = Field(None, title="Purpose", description="What is the facility for?")
    loan_amount: Amount = Field(gt=0, title="Loan amount")
    tenure: Months = Field(title="Tenure", description="In months")
    monthly_repayment: Amount = Field(gt=0, title="Monthly repayment")
    ability_to_repay: LongText | None = Field(
        None, title="Ability to repay", description="Include cover ratio, salary, profit details, etc."
    )
    borrowing_status: LongText | None = Field(
        None,
        title="Borrowing status",
        description="Other loans, with us or elsewhere: tenor, amount, disbursement date, etc.",
    )
    security_vetted: LongText | None = Field(
        None,
        title="Security vetted",
        description="Has the security been vetted, and does it meet the assessment guidelines?",
    )
    overall_assessment: LongText | None = Field(
        None, title="Overall assessment", description="Anything else the approvers should know?"
    )
    referred_by: str | None = Field(None, title="Referred by")
    recommendation: Literal["Approve", "Decline"] = Field(title="Recommendation", description="Yours, personally")
    client_folder: DriveFolder | None = Field(
        None,
        title="Client folder",
        description="In Drive, Shared with me › Client Folders: right-click the client's folder, then Share › Copy link",
        json_schema_extra={"help_image": "client-folder.png"},
    )


class WriteOffForm(BaseModel):
    model_config = ConfigDict(extra="forbid", title="Write-off")

    client_first_name: str = Field(min_length=1, title="Client's first name")
    client_last_name: str = Field(min_length=1, title="Client's last name")
    client_other_names: str | None = Field(None, title="Client's other names")
    client_number: AccountNumber = Field(
        title="Client number", description="The client's account number in Mifos, e.g. 000000123"
    )
    loan_account_number: AccountNumber = Field(
        title="Loan account number", description="The loan's account number in Mifos, e.g. 000000428"
    )
    # In the order a request makes its case: what was lent and at what interest, over how long, what's come back,
    # what's left
    original_principal: Amount = Field(
        gt=0, title="Original principal", description="What was lent, before interest and fees"
    )
    original_interest: Amount = Field(
        title="Original interest", description="The interest charged on the loan over its term"
    )
    loan_term: Months = Field(title="Loan term", description="In months")
    total_recovered: Amount = Field(
        title="Total recovered", description="Everything received on the loan so far, interest and fees included"
    )
    current_balance: Amount = Field(
        gt=0, title="Current balance", description="What's still owed: the amount to be written off"
    )
    justification: LongText = Field(
        min_length=1,
        title="Justification",
        description="What changed for the client, and why the rest can't be recovered",
    )
    supporting_documents: FileRefs = Field(
        [],
        title="Supporting documents",
        description="Mifos screenshots, statements, letters: anything that backs it up",
    )


# The Google Forms' questions
VEHICLE_LOG = {
    "trip_name_purpose": "Trip Name / Purpose",
    "destination": "Destination",
    "vehicle": "Vehicle",
    "drivers": "Driver(s)",
    "purpose_category": "Purpose Category",
    "trip_start_date": "Trip Start Date",
    "trip_start_time": "Trip Start Time",
    "trip_end_date": "Trip End Date",
    "trip_end_time": "Trip End Time",
    "odometer_start_reading": "Odometer Start Reading",
    "odometer_end_reading": "Odometer End Reading",
    "total_distance": "Total Distance",
    "fuel_reading_start": "Fuel Reading (Start)",
    "fuel_reading_end": "Fuel Reading (End)",
    "was_refueled": "Was the vehicle refueled at any point during this trip?",
    "was_fixed": "Was the vehicle fixed / checked / maintained during this trip?",
    "was_fixed_description": "Fix / Check / Maintenance Description",
    "issues": "Issues",
    "issues_description": "Issues Description",
    "comment": "Comment",
    "vehicle_images": "Vehicle Images",
}

LOAN_APPROVAL = {
    "applicant_first_name": "Applicant First Name",
    "applicant_last_name": "Applicant Last Name",
    "applicant_other_names": "Applicant Other Names",
    "character_assessment": "Character - What's your assessment of the client's character?",
    "purpose": "What is the purpose of the facility?",
    "loan_amount_and_tenure": "Loan amount and tenure?",
    "monthly_repayment": "What would be the monthly repayment?",
    "applicant_ability": (
        "What is the client's ability to service the loan? Include cover ratio, salary, profit details etc."
    ),
    "applicant_borrowing_status": (
        "What is the client's current borrowing status? e.g. Do they have other loans with us or other "
        "institutions? What are the details of these loans i.e. tenor, amount, disbursement date, etc"
    ),
    "has_security_vetted": "Has the security been vetted and meet the requirements as per the assessment guidelines?",
    "refferer": "Who referred the client",
    "submitter_recommendation": 'What is your personal recommendation e.g. "Approve/Disapprove"',
    "overall_assessment": "Overall assessment (anything else that you would you like the approvers to know?)",
    "client_folder": "Link to Applicant Client Folder",
}

WRITE_OFF = {
    "client_full_name": "Client Full Name",
    "client_number": "Client Number",
    "loan_account_number": "Loan Account Number",
    "original_principal": "Original Principal",
    "loan_term": "Loan Term",
    "total_recovered": "Total Amount Recovered",
    "current_balance": "Current Account Balance",
    "outstanding_instalments": "Outstanding Instalments",
    "reason": "Reason",
    "justification": "Why should it be written off?",
    "supporting_documents": "Supporting Documents",
}

FORMS = {
    "requisition": Form(
        collection="requisitions",
        workflow="expense",
        model=RequisitionForm,
        submission=Requisition,
        google_form=GoogleForm(model=Requisition),
        title="Requisitions",
        noun="requisition",
        taker="an accountant",
        subject=("payable_to",),
        tracks_status=True,
    ),
    "vehicle_log": Form(
        collection="vehicle_logs",
        workflow="intake",
        model=VehicleLogForm,
        google_form=GoogleForm(
            model=text_form("VehicleLog", VEHICLE_LOG, ("trip_name_purpose",), ("vehicle_images",)),
            labels=VEHICLE_LOG,
            files=("vehicle_images",),
        ),
        title="Vehicle logs",
        noun="vehicle log",
        taker="someone",
        subject=("trip_name_purpose", "purpose"),
    ),
    "loan_approval": Form(
        collection="loan_approvals",
        workflow="intake",
        model=LoanApprovalForm,
        google_form=GoogleForm(
            model=text_form("LoanApproval", LOAN_APPROVAL, ("applicant_first_name", "applicant_last_name")),
            labels=LOAN_APPROVAL,
        ),
        title="Loan approvals",
        noun="loan approval request",
        taker="a director",
        subject=("applicant_first_name", "applicant_last_name"),
    ),
    "write_off": Form(
        collection="write_offs",
        workflow="intake",
        model=WriteOffForm,
        google_form=GoogleForm(
            model=text_form("WriteOff", WRITE_OFF, ("client_full_name",), ("supporting_documents",)),
            labels=WRITE_OFF,
            files=("supporting_documents",),
        ),
        title="Write-offs",
        noun="write-off request",
        taker="a director",
        subject=("client_full_name", "client_first_name", "client_last_name"),
    ),
}
