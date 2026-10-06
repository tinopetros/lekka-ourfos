"""What only a requisition's workflow, expense, does: classify, suggest, post, read back and confirm. Receiving,
acknowledging and handing over are every form's (routers/forms.py)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

import emails
import store
from classify import attachments, expenser
from common import log, simulate
from integrations import mifos
from requisition import Requisition
from routers.forms import email, run_id, send

FORM = "requisition"
# A post with no date disbursed is booked on the day it's posted, ours: UTC+2, with no daylight saving
HARARE = timezone(timedelta(hours=2))
router = APIRouter(prefix=f"/forms/{FORM}/{{id}}")


def run(id: str) -> store.Doc:
    return store.run(FORM, id, run_id())


@router.post("/classify")
async def classify(id: str, body: dict):
    code = body.get("simulate")
    requisition = Requisition.model_validate((await run_in_threadpool(store.submission(FORM, id).get))["answers"])
    amount = requisition.amount
    if code:
        # "stub", or a forced failure. In a thread, so a simulated hang can't block the event loop. No files fetched,
        # except for "files": fetched for real, then the canned answer, so a fixture covers the fetch without the model
        await run_in_threadpool(simulate, "classify", code)
        if code == "files":
            await attachments.load(requisition)
        classification = stub(amount, code)
    else:
        # The agent fetches the files, in memory for this request only. The document keeps the refs it already had
        classification = await expenser.classify(requisition)

    await run_in_threadpool(run(id).save, status="classified", classification=classification)
    log("classify", amount=amount, approve=classification["approve"], by="stub" if code else "expenser")
    return classification


def stub(amount: float, code: str) -> dict:
    if code == "rejected":
        return {
            "approve": False,
            "reason": "Stub: salaries are not ours to file",
            "debit": [],
            "credit": [],
            "comments": [],
        }
    return {
        "approve": True,
        "reason": "Stub: approved",
        "debit": [line("Advertising and Promotions", "5020", 66, "EXPENSE", amount)],
        # "unbalanced" gives check something to catch
        "credit": [line("Cash at Vault", "10000000", 109, "ASSET", amount - (1 if code == "unbalanced" else 0))],
        "comments": ["Stub: a canned answer"],
    }


def line(name: str, gl_code: str, gl_id: int, account_type: str, amount: float) -> dict:
    return {"name": name, "glCode": gl_code, "glId": gl_id, "accountType": account_type, "amount": amount}


@router.post("/suggest")
def suggest(id: str, body: dict):
    this = run(id)
    doc = this.get()
    if sent := doc.get("emails", {}).get("suggestion"):
        return sent
    simulate("suggest", body.get("simulate"))
    requisition = Requisition.model_validate(store.submission(FORM, id).get()["answers"])
    html, text = emails.suggestion(doc["classification"])
    sent = send(
        FORM,
        "suggestion",
        requisition.submitted_by,
        emails.LEKKAI,
        emails.subject(FORM, requisition.payable_to, requisition.response_number, doc.get("test")),
        html,
        text,
        body["thread"],
        doc.get("test"),
    )
    this.record(emails={"suggestion": email(sent)})
    return sent


@router.post("/post")
def post(id: str, body: dict):
    # "unrecorded" posts, to the stub, then fails the write that follows
    code = body.get("simulate")
    this = run(id)
    doc = this.get()
    # Never twice: a retried post finds the first's transaction
    if posted := doc.get("mifos_transaction_id"):
        return {"mifos_transaction_id": posted}
    # A test run never posts, on dev or prod (docs/release1/adr.md 3)
    if doc.get("test"):
        log("not posted: a test run")
        return {"skipped": "test"}
    requisition = Requisition.model_validate(store.submission(FORM, id).get()["answers"])
    classification = doc["classification"]
    # The requisition's own reference, the response number until the form asks for one. First in the comments too,
    # then what else finds it: the subject, the response number and the run
    reference = requisition.reference_number or str(requisition.response_number)
    posted = mifos.post(
        reference,
        classification["debit"],
        classification["credit"],
        requisition.disbursed_on or datetime.now(HARARE).date(),
        f"Reference number: {reference}. "
        f"{emails.subject(FORM, requisition.payable_to, requisition.response_number)}. "
        f"Response number: {requisition.response_number}. Workflow run: {this.ref.id}",
        "stub" if code == "unrecorded" else code,
    )
    this.record(fail=code == "unrecorded", status="posted", mifos_transaction_id=posted["mifos_transaction_id"])
    return posted


@router.get("/read-back/{mifos_transaction_id}")
def read_back(id: str, mifos_transaction_id: str, code: str | None = Query(None, alias="simulate")):
    # What Mifos has, kept for the last email, and what differs from what we posted
    this = run(id)
    classification = this.get()["classification"]
    entry = mifos.read_back(mifos_transaction_id, classification["debit"], classification["credit"], code)
    this.record(posted=entry["posted"])
    return entry


@router.post("/confirm")
def confirm(id: str, body: dict):
    """The last email: what Mifos has and its transaction id, or, for a test run, that nothing was posted."""
    this = run(id)
    doc = this.get()
    if sent := doc.get("emails", {}).get("confirmation"):
        return sent
    simulate("confirm", body.get("simulate"))
    requisition = Requisition.model_validate(store.submission(FORM, id).get()["answers"])
    if transaction := body.get("mifos_transaction_id"):
        html, text = emails.confirmation(doc["posted"]["lines"], transaction)
    else:
        html, text = emails.not_posted(doc["classification"])
    sent = send(
        FORM,
        "confirmation",
        requisition.submitted_by,
        emails.LEKKAI,
        emails.subject(FORM, requisition.payable_to, requisition.response_number, doc.get("test")),
        html,
        text,
        body["thread"],
        doc.get("test"),
    )
    this.record(emails={"confirmation": email(sent)})
    return sent
