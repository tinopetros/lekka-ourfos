"""What the API answers with: one model per route, and the UI's TypeScript types are generated from them
(docs/phase13/adr.md 4). Firestore enforces no schema, so these are the only definition of what a list or a sheet
holds: a field the store lacks is None here, never an error."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    # A field with a default is still always in the answer: TypeScript gets `x: T | null`, never `x?: T | null`
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Me(Model):
    """Who's signed in, and where: one call before anything shows (docs/phase13/adr.md 8)."""

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
    # Drive's, opened in Drive. A gs:// file has nowhere to open yet
    url: str | None = None


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


class Run(Model):
    """One workflow run on a submission: the run that took it in, or a correction."""

    id: str
    workflow: str | None = None
    status: str | None = None
    test: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # Why it was handed over, rejected or refused
    reason: str | None = None
    emails: list[Email] = []
    classification: Classification | None = None
    mifos_transaction_id: str | None = None
    # A posting that was turned off or skipped says why
    skipped: str | None = None
    posted: list[Line] = []
    # A correction's: what it was asked, the entry it corrected, and that entry's mirror
    request: CorrectionRequest | None = None
    entry: str | None = None
    reversal: str | None = None


class JournalEntry(Model):
    """One Mifos transaction we posted (docs/phase12/tdd.md, step 2)."""

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
    # A mirror was posted without hearing back: check Mifos (docs/phase12/adr.md 4)
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
