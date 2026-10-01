"""What only a requisition's workflow, expense, does: classify, suggest, post and confirm. Receiving,
acknowledging and handing over are every form's (routers/forms.py)."""

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
router = APIRouter(prefix=f"/forms/{FORM}/{{id}}")


def run(id: str) -> store.Doc:
    return store.run(FORM, id, run_id())


def requisition(id: str) -> Requisition:
    return Requisition.model_validate(store.submission(FORM, id).get()["answers"])


@router.post("/classify")
async def classify(id: str, body: dict):
    code = body.get("simulate")
    # Firestore's client blocks, and this route is async, so in a thread: the event loop serves every other request
    r = await run_in_threadpool(requisition, id)
    amount = r.amount
    if code:
        # "stub", or a forced failure. In a thread, so a simulated hang can't block the event loop. No files fetched,
        # except for "files": fetched for real, then the canned answer, so a fixture covers the fetch without the model
        await run_in_threadpool(simulate, "classify", code)
        if code == "files":
            await attachments.load(r)
        classification = stub(amount, code)
    else:
        # The agent fetches the files, in memory for this request only. The document keeps the refs it already had
        classification = await expenser.classify(r)

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
    r = requisition(id)
    html, text = emails.suggestion(doc["classification"])
    sent = send(
        FORM,
        "suggestion",
        r.submitted_by,
        emails.LEKKAI,
        emails.subject(FORM, r.payable_to, r.response_number, doc.get("test")),
        html,
        text,
        body["thread"],
        doc.get("test"),
    )
    this.record(emails={"suggestion": email(sent)})
    return sent


@router.post("/post")
def post(id: str, body: dict):
    # "unrecorded" posts, then fails the write that follows
    code = body.get("simulate")
    this = run(id)
    classification = this.get()["classification"]
    # The run's id is the reference Mifos keeps, as it was before a submission had runs
    posted = mifos.post(
        this.ref.id, classification["debit"], classification["credit"], None if code == "unrecorded" else code
    )
    this.record(fail=code == "unrecorded", status="posted", mifos_transaction_id=posted["mifos_transaction_id"])
    return posted


@router.get("/read-back/{mifos_transaction_id}")
def read_back(id: str, mifos_transaction_id: str, code: str | None = Query(None, alias="simulate")):
    # The stub echoes what we posted. Real Mifos will answer from the ledger
    classification = run(id).get()["classification"]
    return mifos.read_back(mifos_transaction_id, classification["debit"], classification["credit"], code)


@router.post("/confirm")
def confirm(id: str, body: dict):
    # Mifos is a stub: an email confirming a post that didn't happen would be a lie (phase 9 ADR 6)
    simulate("confirm", body.get("simulate"))
    log("confirm: no email while Mifos is a stub", mifos_transaction_id=body["mifos_transaction_id"])
    return {"sent": False}
