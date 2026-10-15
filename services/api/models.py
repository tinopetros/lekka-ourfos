from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    # A field with a default is still always in the answer: TypeScript gets `x: T | null`, never `x?: T | null`
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Me(Model):
    """Who's signed in, and where: one call before anything shows."""

    email: str
    environment: Literal["local", "dev", "prod"]
    # The commit the image was built from, for bug reports
    version: str


class FormInfo(Model):
    key: str
    title: str


class SubmissionSummary(Model):
    """A row in a form's list: what it is, who sent it, and where it stands."""

    id: str
    form: str
    response_number: int | None = None
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    # When we first had it, valid or not: lists sort by it
    received_at: datetime | None = None
    updated_at: datetime | None = None
    status: str | None = None
    test: bool = False
    # What the subject names: a payee, a trip, an applicant
    title: str | None = None
    # Requisitions only, once posted
    amount: float | None = None
    live_entry: str | None = None


class File(Model):
    name: str
    # Drive's, by its id: Drive's own preview shows it to whoever's Google account can open it
    drive_id: str | None = None
    # Ours, by its gs:// ref: the API streams it, at /api/files
    ref: str | None = None


class Answer(Model):
    """One of the form's questions, in its order. Empty ones are left out."""

    label: str
    text: str | None = None
    # A lone link, like a loan's client folder
    link: str | None = None
    files: list[File] = []


class Line(Model):
    name: str
    glCode: str | None = None
    glId: int | None = None
    amount: float
    type: Literal["DEBIT", "CREDIT"] | None = None


class Email(Model):
    kind: str
    at: datetime | None = None
    message_id: str | None = None


class Classification(Model):
    """What expenser decided, and why."""

    approve: bool | None = None
    reason: str | None = None
    comments: list[str] = []
    debit: list[Line] = []
    credit: list[Line] = []


class CorrectionRequest(Model):
    reason: str | None = None
    requested_by: str | None = None
    transaction_id: str | None = None
    debit: list[Line] = []
    credit: list[Line] = []


class RunBase(Model):
    """What every workflow's run has: what it is, how it ended, and the emails it sent."""

    id: str
    status: str | None = None
    test: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # Why it was handed over, rejected or refused
    reason: str | None = None
    emails: list[Email] = []


class ExpenseRun(RunBase):
    """A requisition taken in: expenser's call, and what was posted to Mifos."""

    workflow: Literal["expense"] = "expense"
    classification: Classification | None = None
    mifos_transaction_id: str | None = None
    # Posting turned off by the trigger says so
    skipped: str | None = None
    posted: list[Line] = []


class CorrectionRun(RunBase):
    """A posted requisition corrected: what was asked, the entry it reversed, its mirror, and what was posted."""

    workflow: Literal["correction"] = "correction"
    request: CorrectionRequest | None = None
    entry: str | None = None
    reversal: str | None = None
    mifos_transaction_id: str | None = None
    posted: list[Line] = []


class IntakeRun(RunBase):
    """A form only received and acknowledged."""

    workflow: Literal["intake"] = "intake"


class UnknownRun(RunBase):
    """A run of a workflow this API doesn't know yet: how it ended, and what the store calls it."""

    workflow: Literal["unknown"] = "unknown"
    name: str | None = None


# Which a run is, by its workflow: TypeScript narrows on `run.workflow` to each one's own fields
Run = Annotated[ExpenseRun | CorrectionRun | IntakeRun | UnknownRun, Field(discriminator="workflow")]


class JournalEntry(Model):
    """One Mifos transaction we posted."""

    transaction_id: str
    transaction_date: str | None = None
    created_on: str | None = None
    currency: str | None = None
    reference_number: str | None = None
    comments: str | None = None
    lines: list[Line] = []
    source: str | None = None
    by: str | None = None
    status: str | None = None
    reverses: str | None = None
    reversed_by: str | None = None
    # A mirror was posted without hearing back: check Mifos
    reversing: str | None = None
    form: str | None = None
    submission: str | None = None
    run: str | None = None
    recorded_at: datetime | None = None


class Submission(SubmissionSummary):
    """What a row opens: the answers, every run on it, and the entries it posted."""

    answers: list[Answer] = []
    # The webhook's body, when the answers never validated: all there is to see
    raw: dict | None = None
    runs: list[Run] = []
    journal_entries: list[JournalEntry] = []


class SubmissionPage(Model):
    items: list[SubmissionSummary]
    # The next page's cursor, or None on the last
    next: str | None = None


class JournalEntryPage(Model):
    items: list[JournalEntry]
    next: str | None = None
