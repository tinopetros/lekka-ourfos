"""Every form we take: where it's stored, which workflow runs it, and what its emails call it (docs/phase10/tdd.md).

The three that are only received and acknowledged keep their answers as text, strict only where the subject needs
them (docs/phase10/adr.md 4). Their keys are the webhook's own, and their labels the form's questions, in the
form's order: the add-on's emails listed them so. Not the response sheet's, where a question added later is last. Copied into the trigger's zip, so it only imports pydantic.
"""

from dataclasses import dataclass, field

from pydantic import Field, create_model

from requisition import Requisition
from submission import Submission


@dataclass(frozen=True)
class Form:
    collection: str
    workflow: str
    model: type[Submission]
    # What a handover calls it, and who takes it from there
    noun: str
    taker: str
    # The answers the subject names, after the form's name, joined by a space
    subject: tuple[str, ...]
    # Text forms only: key to question, in the form's order
    labels: dict[str, str] = field(default_factory=dict)
    files: tuple[str, ...] = ()


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
    "client_folder": "Link to Applicant Client Folder (see example below)",
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
        model=Requisition,
        noun="requisition",
        taker="an accountant",
        subject=("payable_to",),
    ),
    "vehicle_log": Form(
        collection="vehicle_logs",
        workflow="intake",
        model=text_form("VehicleLog", VEHICLE_LOG, ("trip_name_purpose",), ("vehicle_images",)),
        noun="vehicle log",
        taker="someone",
        subject=("trip_name_purpose",),
        labels=VEHICLE_LOG,
        files=("vehicle_images",),
    ),
    "loan_approval": Form(
        collection="loan_approvals",
        workflow="intake",
        model=text_form("LoanApproval", LOAN_APPROVAL, ("applicant_first_name", "applicant_last_name")),
        noun="loan approval request",
        taker="a director",
        subject=("applicant_first_name", "applicant_last_name"),
        labels=LOAN_APPROVAL,
    ),
    "write_off": Form(
        collection="write_offs",
        workflow="intake",
        model=text_form("WriteOff", WRITE_OFF, ("client_full_name",), ("supporting_documents",)),
        noun="write-off request",
        taker="a director",
        subject=("client_full_name",),
        labels=WRITE_OFF,
        files=("supporting_documents",),
    ),
}
