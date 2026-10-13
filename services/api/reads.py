"""Firestore's documents as the API's models. Pure: a document in, a model out, so every shape a document has had is
tested without a database. What the store lacks is None, never an error: an invalid submission has no answers."""

from pydantic import ValidationError

from common import log
from forms import FORMS
from requisition import Requisition

from .models import (
    Answer,
    Classification,
    CorrectionRequest,
    Email,
    File,
    JournalEntry,
    Line,
    Run,
    Submission,
    SubmissionSummary,
)

# Their questions' titles on the form, for the requisition's fields with files, as its emails have them
FILE_LABELS = {"signed_requisition_form": "Signed Requisition Form", "receipts": "Receipt(s)", "invoices": "Invoice(s)"}


def title(form: str) -> str:
    """What the sidebar calls a form's list: Requisitions, Vehicle logs."""
    return f"{FORMS[form].noun[0].upper()}{FORMS[form].noun[1:]}s"


def summary(form: str, id: str, doc: dict) -> SubmissionSummary:
    answers = doc.get("answers") or {}
    named = " ".join(str(answers[k]).strip() for k in FORMS[form].subject if answers.get(k))
    return SubmissionSummary(
        id=id,
        form=form,
        response_number=doc.get("response_number", answers.get("response_number")),
        submitted_by=doc.get("submitted_by", answers.get("submitted_by")),
        submitted_at=doc.get("submitted_at", answers.get("submitted_at")),
        updated_at=doc.get("updated_at"),
        status=doc.get("status"),
        test=bool(doc.get("test")),
        title=named or None,
        amount=answers.get("amount") if form == "requisition" else None,
        live_entry=doc.get("live_entry"),
    )


def files(refs: list[str]) -> list[File]:
    """File 1, File 2, as the emails name them. Drive's open in Drive."""
    return [
        File(name=f"File {n}", url=None if ref.startswith("gs://") else f"https://drive.google.com/open?id={ref}")
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
            rows.append(Answer(label=FILE_LABELS[field], files=files(refs)))
    return rows


def lines(xs: list[dict] | None) -> list[Line]:
    return [Line.model_validate(x) for x in xs or []]


def posted(value) -> list[Line]:
    """What a run posted: the lines it sent, or phase 11's, which kept the lines Mifos read back as a list."""
    return lines(value if isinstance(value, list) else (value or {}).get("lines"))


def run(id: str, doc: dict) -> Run:
    """One run, however much of it there is. A shape this doesn't know still shows its workflow and how it ended."""
    try:
        return _run(id, doc)
    except (AttributeError, TypeError, ValueError) as e:
        log(f"run shown in part: {e}", "WARNING", run=id)
        return Run(id=id, workflow=str(doc.get("workflow") or "") or None, status=str(doc.get("status") or "") or None)


def _run(id: str, doc: dict) -> Run:
    execution = doc.get("execution") or {}
    classification = doc.get("classification")
    request = doc.get("request")
    emails = sorted(
        (
            Email(kind=kind, at=e.get("at"), message_id=e.get("message_id"))
            for kind, e in (doc.get("emails") or {}).items()
        ),
        key=lambda e: (e.at is None, e.at),
    )
    return Run(
        id=id,
        workflow=doc.get("workflow"),
        status=doc.get("status"),
        test=bool(doc.get("test")),
        started_at=execution.get("started_at"),
        completed_at=execution.get("completed_at"),
        reason=doc.get("reason") if isinstance(doc.get("reason"), str) else None,
        emails=emails,
        classification=Classification(
            approve=classification.get("approve"),
            reason=classification.get("reason"),
            comments=classification.get("comments") or [],
            debit=lines(classification.get("debit")),
            credit=lines(classification.get("credit")),
        )
        if classification
        else None,
        mifos_transaction_id=doc.get("mifos_transaction_id"),
        # Posting turned off by the trigger (docs/phase12/adr.md 8)
        skipped="mifos" if doc.get("mifos") is False else None,
        posted=posted(doc.get("posted")),
        request=CorrectionRequest(
            reason=request.get("reason"),
            requested_by=request.get("requested_by"),
            transaction_id=request.get("transaction_id"),
            debit=lines(request.get("debit")),
            credit=lines(request.get("credit")),
        )
        if request
        else None,
        entry=doc.get("entry"),
        reversal=(doc.get("reversal") or {}).get("transaction_id"),
    )


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
