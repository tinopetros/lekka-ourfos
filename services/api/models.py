from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    # A field with a default is still always in the answer: TypeScript gets `x: T | null`, never `x?: T | null`
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Person(Model):
    """Someone, as the UI shows them: by name, the email beside it."""

    email: str
    name: str | None


class Me(Model):
    """Who's signed in, and where: one call before anything shows."""

    email: str
    # Workspace's, if it has one
    name: str | None = None
    environment: Literal["local", "dev", "prod"]
    # The commit the image was built from, for bug reports
    version: str
    # What you may do, from the policy: the UI offers only these, and the API checks either way
    permissions: list[str]


class FormInfo(Model):
    key: str
    title: str
    # Whether its status means anything: the others only show they were received
    tracks_status: bool


class SubmitRequest(BaseModel):
    """What our own form sends: its answers, checked against the form's model, and whether it's a test."""

    answers: dict[str, Any]
    test: bool = False


class ReverseRequest(BaseModel):
    """Which entry, so a page that's out of date can't reverse a newer one, and why: the reply in its thread says."""

    transaction_id: str
    reason: str


class Account(Model):
    """A GL account a correction can post to, as Mifos has it."""

    glId: int
    glCode: str
    name: str
    type: str
    # One expenser picks from: listed first
    expenser: bool


class CorrectedLine(BaseModel):
    """An account and an amount: the rest of the line is Mifos's, looked up."""

    glId: int
    amount: Annotated[float, Field(gt=0)]


class CorrectedLines(BaseModel):
    debit: Annotated[list[CorrectedLine], Field(min_length=1)]
    credit: Annotated[list[CorrectedLine], Field(min_length=1)]


class CorrectRequest(ReverseRequest):
    """A reversal's, and the lines posted after it."""

    lines: CorrectedLines


class PostRequest(BaseModel):
    """Lines for a requisition with nothing live, and where Mifos files them: no reason, since it corrects nothing."""

    lines: CorrectedLines
    reference: str
    transaction_date: date
    comments: str


class Posting(Model):
    """What a requisition with nothing live would be posted as, from its answers, as Lekkai would have: each as the
    dialog starts, None where the requisition doesn't say. Its tenant is demo for a test, else None, the
    environment's own"""

    reference: str | None
    transaction_date: date | None
    comments: str
    tenant: str | None = None


class ActionRequest(BaseModel):
    """What's done to a submission, said in its thread with its comment, and any files that show it: refs from
    uploading them first. Approve and comment are for loan approvals and write-offs; close is for them and
    requisitions."""

    kind: Literal["approve", "close", "comment"]
    comment: str = ""
    files: list[str] = []


class Acting(Model):
    """The action's run: the page asks how it went until it ends."""

    run: str


class ActionState(Model):
    """How an action's run went: running, done or failed, and why, if it failed."""

    state: Literal["running", "done", "failed"]
    reason: str | None = None


class Action(Model):
    """What a person did to a submission from the UI, once its thread was told. Done and disapprove, kept on dev
    before Post journal entry and close, still show"""

    id: str
    kind: str
    by: str
    comment: str
    files: list[str] = []
    at: datetime | None = None


class Reversing(Model):
    """The correction run that reverses it: the page watches it until it ends."""

    run: str


class DraftRequest(BaseModel):
    """Our own form as it's being filled in: anything, as typed. The form's model is the submit's."""

    values: dict[str, Any]
    # The same, as the form would submit them: what's looked over, never stored
    answers: dict[str, Any] | None = None
    test: bool = False


class Problem(Model):
    """What's wrong, and where: a question's name, or nothing for the whole form."""

    loc: list[str | int]
    msg: str


class Draft(Model):
    id: str
    title: str | None = None
    updated_at: datetime | None = None
    # What submitting it as it is would find wrong. It's saved either way
    problems: list[Problem] = []


class Uploaded(Model):
    ref: str


class Submitted(Model):
    id: str
    response_number: int


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
    # Where it opens: Drive's in Drive, ours as its emails link it
    url: str


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
    # A run with posting off says so
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
    # The Mifos tenant it's in: demo for a test run's, on prod too
    tenant: str | None = None
    # A test submission's: left out of the journal unless asked for
    test: bool = False
    # A mirror was posted without hearing back: check Mifos
    reversing: str | None = None
    form: str | None = None
    submission: str | None = None
    run: str | None = None
    recorded_at: datetime | None = None


class Submission(SubmissionSummary):
    """What a row opens: the answers, every run on it, and the entries it posted."""

    answers: list[Answer] = []
    # A draft's answers as they were typed, for its form to pick up again. Only its author ever sees one
    draft: dict[str, Any] | None = None
    # The webhook's body, when the answers never validated: all there is to see
    raw: dict | None = None
    runs: list[Run] = []
    journal_entries: list[JournalEntry] = []
    # What people did to it, the newest first
    actions: list[Action] = []
    # A requisition's, while nothing is live and it isn't closed
    posting: Posting | None = None


class SubmissionPage(Model):
    items: list[SubmissionSummary]
    # The next page's cursor, or None on the last
    next: str | None = None


class JournalEntryPage(Model):
    items: list[JournalEntry]
    next: str | None = None
