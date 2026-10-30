"""What the correction workflow does to a posted requisition: post its live entry's mirror, then the corrected lines,
and reply in its thread (docs/phase12/tdd.md, step 4).

A run of its own on the submission, beside the run that posted (docs/phase12/adr.md 3). Each step is safe to retry:
what it did is on the run, and a retried post finds it.
"""

from datetime import date

from fastapi import APIRouter, HTTPException

import emails
import journal
import store
from common import log, simulate
from integrations import mifos
from requisition import Requisition
from routers.forms import email, run_id, send
from routers.requisitions import FORM, comments

router = APIRouter(prefix=f"/forms/{FORM}/{{id}}/correction")


def run(id: str) -> store.Doc:
    return store.run(FORM, id, run_id())


@router.post("")
def start(id: str, body: dict):
    """The run, what it was asked, and the entry it corrects. Refused, 409 or 422, when there's nothing to do."""
    reason, requested_by = (body.get("reason") or "").strip(), (body.get("requested_by") or "").strip()
    if not reason or not requested_by:
        raise HTTPException(422, "A correction needs a reason and who asked for it")
    debit, credit = balanced(body.get("lines"))
    submission = store.submission(FORM, id).get()
    this = run(id)
    # Only ever set on dev: the prod workflow drops it
    simulated = {"simulate": body["simulate"]} if body.get("simulate") else {}
    # No status until it posts or ends: a status is the submission's too, and a correction that's refused changes
    # nothing
    this.save(
        **simulated,
        workflow=body.get("workflow"),
        execution={"started_at": store.NOW, "revision": body.get("revision")},
        request={
            "reason": reason,
            "requested_by": requested_by,
            "transaction_id": body.get("transaction_id"),
            "debit": debit,
            "credit": credit,
        },
    )
    entry = correctable(submission, body.get("transaction_id"))
    this.save(entry=entry)
    log("correction started", entry=entry, lines=len(debit) + len(credit))
    # What a handover needs, so the workflow can say what failed in the thread
    return {
        "entry": entry,
        "thread": submission.get("thread"),
        "submission": submission["answers"],
        "test": bool(submission.get("test")),
        "has_lines": bool(debit),
    }


def correctable(submission: dict, given: str | None) -> str:
    """The requisition's live entry, or why it can't be corrected (docs/phase12/adr.md 4)."""
    live = submission.get("live_entry")
    if not live:
        raise HTTPException(409, "Nothing posted to correct")
    if given and given != live:
        raise HTTPException(409, f"Transaction {given} isn't this requisition's live entry, {live} is")
    unsure(journal.entry(live).get(), live)
    return live


def unsure(original: dict, transaction: str):
    """Refuses an entry whose mirror a run posted without hearing back: it may have landed, and a second would reverse
    it twice. It stays so until a person has checked Mifos."""
    if (run := original.get("reversing")) and not original.get("reversed_by"):
        raise HTTPException(
            409,
            f"Correction run {run} may have reversed {transaction} without hearing back. "
            "Check Mifos before correcting it again",
        )


def balanced(lines) -> tuple[list, list]:
    """Corrected lines, if any: accounts and positive amounts, and debits equal to credits."""
    if not lines:
        return [], []
    debit, credit = lines.get("debit") or [], lines.get("credit") or []
    if not debit or not credit:
        raise HTTPException(422, "Corrected lines need a debit and a credit")
    keys = ("name", "glCode", "glId", "amount")
    for x in debit + credit:
        if not isinstance(x, dict) or any(k not in x for k in keys) or not isinstance(x["glId"], int):
            raise HTTPException(422, f"Each line needs {', '.join(keys)}, its glId a number")
        if not isinstance(x["amount"], int | float) or x["amount"] <= 0:
            raise HTTPException(422, "Each line's amount is more than 0")
    if abs(sum(x["amount"] for x in debit) - sum(x["amount"] for x in credit)) > 0.005:
        raise HTTPException(422, "Debits and credits do not balance")
    return [{k: x[k] for k in keys} for x in debit], [{k: x[k] for k in keys} for x in credit]


def said(id: str, this: store.Doc, doc: dict, what: str) -> str:
    """A correction's comments: what it did, why, and who asked, then what finds it."""
    request = doc["request"]
    requisition = Requisition.model_validate(store.submission(FORM, id).get()["answers"])
    return comments(
        requisition,
        this.ref.id,
        f"{what}.",
        f"Reason: {request['reason']}.",
        f"Requested by: {request['requested_by']}.",
    )


@router.post("/reverse")
def reverse(id: str, body: dict):
    """The live entry's mirror, on its date, so the period it's in balances (docs/phase12/adr.md 2)."""
    code = body.get("simulate")
    this = run(id)
    doc = this.get()
    if done := (doc.get("reversal") or {}).get("transaction_id"):
        return {"mifos_transaction_id": done}
    entry = journal.entry(doc["entry"])
    original = entry.get()
    if original.get("reversed_by"):
        raise HTTPException(409, f"{doc['entry']} is already reversed, by {original['reversed_by']}")
    # Whoever set it, this run included, tried and didn't hear back
    unsure(original, doc["entry"])
    debit, credit = journal.sides(original["lines"])
    on = date.fromisoformat(original["transaction_date"])
    reference = original.get("reference_number") or doc["entry"]
    what = said(id, this, doc, f"Reversal of transaction {doc['entry']}")
    # Before posting, and raised if it can't be written: a mirror that may have landed is never posted again
    entry.save(reversing=this.ref.id)
    try:
        posted = mifos.post(reference, credit, debit, on, what, code, original.get("tenant"))
    except HTTPException as e:
        # Certainly not posted, so nothing to check: the entry can be corrected again
        if e.status_code in (422, 503):
            entry.record(reversing=None)
        raise
    transaction = posted["mifos_transaction_id"]
    this.record(reversal={"transaction_id": transaction, "debit": credit, "credit": debit})
    journal.posted(
        FORM,
        id,
        this.ref.id,
        transaction,
        credit,
        debit,
        on,
        reference,
        what,
        reverses=doc["entry"],
        by=doc["request"]["requested_by"],
        tenant=original.get("tenant"),
    )
    return posted


@router.post("/post")
def post(id: str, body: dict):
    """The corrected lines, on the reversed entry's date. Never twice: a retried post finds the first's"""
    code = body.get("simulate")
    this = run(id)
    doc = this.get()
    if done := doc.get("mifos_transaction_id"):
        return {"mifos_transaction_id": done}
    request = doc["request"]
    if not request["debit"]:
        return {"skipped": "reversal only"}
    original = journal.entry(doc["entry"]).get()
    on = date.fromisoformat(original["transaction_date"])
    reference = original.get("reference_number") or doc["entry"]
    what = said(id, this, doc, f"Correction of transaction {doc['entry']}")
    posted = mifos.post(reference, request["debit"], request["credit"], on, what, code, original.get("tenant"))
    transaction = posted["mifos_transaction_id"]
    this.record(
        status="posted",
        mifos_transaction_id=transaction,
        posted=journal.sent(transaction, request["debit"], request["credit"], on),
    )
    journal.posted(
        FORM,
        id,
        this.ref.id,
        transaction,
        request["debit"],
        request["credit"],
        on,
        reference,
        what,
        by=request["requested_by"],
        tenant=original.get("tenant"),
    )
    return posted


@router.post("/confirm")
def confirm(id: str, body: dict):
    """A reply in the requisition's thread: the new entry and why, or that it was reversed and nothing re-posted."""
    this = run(id)
    doc = this.get()
    if sent := doc.get("emails", {}).get("correction"):
        return sent
    simulate("confirm", body.get("simulate"))
    submission = store.submission(FORM, id).get()
    requisition = Requisition.model_validate(submission["answers"])
    request = doc["request"]
    if doc.get("mifos_transaction_id"):
        html, text = emails.corrected(
            id,
            doc["posted"],
            doc["entry"],
            doc["reversal"]["transaction_id"],
            request["reason"],
            request["requested_by"],
        )
    else:
        # The mirror as posted, on the reversed entry's date, so its email shows its lines as the page does
        reversal = doc["reversal"]
        on = date.fromisoformat(journal.entry(doc["entry"]).get()["transaction_date"])
        posted = journal.sent(reversal["transaction_id"], reversal["debit"], reversal["credit"], on)
        html, text = emails.reversed_only(id, posted, doc["entry"], request["reason"], request["requested_by"])
    test = submission.get("test")
    sent = send(
        FORM,
        "correction",
        requisition.submitted_by,
        emails.LEKKAI,
        emails.subject(FORM, requisition.payable_to, requisition.response_number, test),
        html,
        text,
        body["thread"],
        test,
    )
    this.record(emails={"correction": email(sent)})
    return sent
