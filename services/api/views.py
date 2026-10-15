"""Turns what Firestore stores into what the API sends. Stored documents have changed shape over the phases, and some
lack fields: a submission that failed validation has no answers. So whatever is missing comes back empty, never as an
error. No database here: tests hand it documents of every shape."""

from pydantic import ValidationError

from common import log
from forms import FORMS
from requisition import Files, Requisition

from .models import (
    Answer,
    Classification,
    CorrectionRequest,
    CorrectionRun,
    Email,
    ExpenseRun,
    File,
    IntakeRun,
    JournalEntry,
    Line,
    Run,
    RunBase,
    Submission,
    SubmissionSummary,
    UnknownRun,
)

# Each workflow's run, by the name the store gives it
RUNS: dict[str, type[RunBase]] = {"expense": ExpenseRun, "correction": CorrectionRun, "intake": IntakeRun}


def summary(form: str, id: str, doc: dict) -> SubmissionSummary:
    answers = doc.get("answers") or {}
    named = " ".join(str(answers[k]).strip() for k in FORMS[form].subject if answers.get(k))
    return SubmissionSummary(
        id=id,
        form=form,
        response_number=doc.get("response_number", answers.get("response_number")),
        submitted_by=doc.get("submitted_by", answers.get("submitted_by")),
        submitted_at=doc.get("submitted_at", answers.get("submitted_at")),
        received_at=doc.get("received_at"),
        updated_at=doc.get("updated_at"),
        status=doc.get("status"),
        test=bool(doc.get("test")),
        title=named or None,
        amount=answers.get("amount") if form == "requisition" else None,
        live_entry=doc.get("live_entry"),
    )


def files(refs: list[str]) -> list[File]:
    """File 1, File 2, as the emails name them: Drive's by id, ours by gs:// ref."""
    return [
        File(name=f"File {n}", ref=ref) if ref.startswith("gs://") else File(name=f"File {n}", drive_id=ref)
        for n, ref in enumerate(refs, 1)
    ]


def answers(form: str, doc: dict) -> list[Answer]:
    """The form's questions in its order, empty ones left out, as its first email lists them."""
    values = doc.get("answers") or {}
    if not values:
        return []
    if form == "requisition":
        return requisition_answers(values)
    spec, rows = FORMS[form], []
    for key, label in spec.labels.items():
        value = values.get(key)
        if not value:
            continue
        if key in spec.files:
            rows.append(Answer(label=label, files=files(value)))
        elif str(value).startswith(("http://", "https://")) and " " not in str(value).strip():
            rows.append(Answer(label=label, link=str(value).strip()))
        else:
            rows.append(Answer(label=label, text=str(value)))
    return rows


def requisition_answers(values: dict) -> list[Answer]:
    try:
        r = Requisition.model_validate(values)
    except ValidationError:
        # A shape from before the model was what it is now: every answer as it was kept
        return [Answer(label=k, text=str(v)) for k, v in values.items() if v not in (None, "", [], {})]
    rows = [Answer(label="Reference Number", text=r.reference_number)] if r.reference_number else []
    rows += [Answer(label="Payable To", text=r.payable_to), Answer(label="Total Amount", text=f"${r.amount:,.2f}")]
    if r.disbursed_on:
        rows.append(Answer(label="Date Disbursed", text=r.disbursed_on.isoformat()))
    if r.comment:
        rows.append(Answer(label="Comment", text=r.comment))
    for field, refs in r.files.model_dump().items():
        if refs:
            rows.append(Answer(label=Files.label(field), files=files(refs)))
    return rows


def lines(xs: list[dict] | None) -> list[Line]:
    return [Line.model_validate(x) for x in xs or []]


def posted(value) -> list[Line]:
    """What a run posted: the lines it sent, or phase 11's, which kept the lines Mifos read back as a list."""
    return lines(value if isinstance(value, list) else (value or {}).get("lines"))


def run(id: str, doc: dict) -> Run:
    """One run, as its workflow's shape. A field of a shape this doesn't know leaves only what every run has, so the
    sheet still shows how it ended."""
    name = doc.get("workflow")
    kind = RUNS.get(name)
    base = shared(id, doc)
    if not kind:
        return UnknownRun(**base, name=str(name) if name else None)
    try:
        return kind(**base, **ONLY[kind](doc))
    except (AttributeError, TypeError, ValueError) as e:
        log(f"run shown in part: {e}", "WARNING", run=id)
        return kind(**base)


def shared(id: str, doc: dict) -> dict:
    """What every run has, read as safely as can be: these never fail a sheet."""
    execution = doc.get("execution") if isinstance(doc.get("execution"), dict) else {}
    emails = doc.get("emails") if isinstance(doc.get("emails"), dict) else {}
    return {
        "id": id,
        "status": doc.get("status") if isinstance(doc.get("status"), str) else None,
        "test": bool(doc.get("test")),
        "started_at": execution.get("started_at"),
        "completed_at": execution.get("completed_at"),
        "reason": doc.get("reason") if isinstance(doc.get("reason"), str) else None,
        "emails": sorted(
            (Email(kind=k, at=e.get("at"), message_id=e.get("message_id")) for k, e in emails.items()),
            key=lambda e: (e.at is None, e.at),
        ),
    }


def expense(doc: dict) -> dict:
    c = doc.get("classification")
    return {
        "classification": Classification(
            approve=c.get("approve"),
            reason=c.get("reason"),
            comments=c.get("comments") or [],
            debit=lines(c.get("debit")),
            credit=lines(c.get("credit")),
        )
        if c
        else None,
        "mifos_transaction_id": doc.get("mifos_transaction_id"),
        # Posting turned off by the trigger
        "skipped": "mifos" if doc.get("mifos") is False else None,
        "posted": posted(doc.get("posted")),
    }


def correction(doc: dict) -> dict:
    r = doc.get("request")
    return {
        "request": CorrectionRequest(
            reason=r.get("reason"),
            requested_by=r.get("requested_by"),
            transaction_id=r.get("transaction_id"),
            debit=lines(r.get("debit")),
            credit=lines(r.get("credit")),
        )
        if r
        else None,
        "entry": doc.get("entry"),
        "reversal": (doc.get("reversal") or {}).get("transaction_id"),
        "mifos_transaction_id": doc.get("mifos_transaction_id"),
        "posted": posted(doc.get("posted")),
    }


# What each workflow's run adds to what every run has
ONLY = {ExpenseRun: expense, CorrectionRun: correction, IntakeRun: lambda doc: {}}


def journal_entry(id: str, doc: dict) -> JournalEntry:
    return JournalEntry.model_validate({"transaction_id": id} | doc | {"lines": lines(doc.get("lines"))})


def submission(form: str, id: str, doc: dict, runs: list[Run], entries: list[JournalEntry]) -> Submission:
    """The sheet: the row, its answers, every run newest first, and its entries in the order they were posted."""
    shown = answers(form, doc)
    return Submission(
        **summary(form, id, doc).model_dump(),
        answers=shown,
        raw=None if shown else doc.get("raw"),
        runs=sorted(runs, key=lambda r: (r.started_at is not None, r.started_at), reverse=True),
        journal_entries=entries,
    )
