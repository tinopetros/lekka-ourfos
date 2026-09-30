"""The requisition workflow's one service. It owns the requisition's document and calls everything else for it."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

import emails
import store
from classify import expenser
from common import RETRIED, log, simulate
from integrations import mifos
from integrations.workspace import gmail
from integrations.workspace.delegation import WorkspaceError
from requisition import Requisition

router = APIRouter(prefix="/requisitions/{id}")


@router.post("")
def receive(id: str, body: dict):
    # Cleaned by the trigger already. A failure here is ours, so a 500 that hands over
    requisition = Requisition.model_validate(body["requisition"])
    # Only ever set on dev: the prod workflow drops it
    simulate = {"simulate": body["simulate"]} if body.get("simulate") else {}
    store.save(
        id,
        **simulate,
        requisition=requisition.to_firestore(),
        raw=body.get("raw"),
        test=bool(body.get("test")),
        response_number=requisition.response_number,
        status="received",
        execution={"id": id, "revision": body.get("revision"), "started_at": store.NOW},
    )
    log("received", response_number=requisition.response_number)
    return {"status": "received"}


@router.post("/classify")
async def classify(id: str, body: dict):
    code = body.get("simulate")
    requisition = Requisition.model_validate((await run_in_threadpool(store.get, id))["requisition"])
    amount = requisition.amount
    if code:
        # "stub", or a forced failure. In a thread, so a simulated hang can't block the event loop. No files fetched
        await run_in_threadpool(simulate, "classify", code)
        classification = stub(amount, code)
    else:
        # The agent fetches the files, in memory for this request only. The document keeps the refs it already had
        classification = await expenser.classify(requisition)

    await run_in_threadpool(store.save, id, status="classified", classification=classification)
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


@router.post("/acknowledge")
def acknowledge(id: str, body: dict):
    """The first email, which starts the thread every other email replies in."""
    doc = store.get(id)
    sent = doc.get("emails", {}).get("acknowledgement")
    if not sent:
        simulate("acknowledge", body.get("simulate"))
        requisition = Requisition.model_validate(doc["requisition"])
        html, text = emails.acknowledgement(requisition)
        sent = send(
            "acknowledgement",
            requisition.submitted_by,
            emails.form_name(),
            emails.subject(requisition.payable_to, requisition.response_number, doc.get("test")),
            html,
            text,
            test=doc.get("test"),
        )
        store.record(id, emails={"acknowledgement": email(sent)})
    # Its Message-ID too, so replies thread in any client. Read after the send is recorded: a retry never resends
    thread = doc.get("thread") or {
        "thread_id": sent["thread_id"],
        "in_reply_to": gmail_call(gmail.rfc822_id, sent["message_id"]),
    }
    store.record(id, thread=thread)
    return thread


@router.post("/suggest")
def suggest(id: str, body: dict):
    doc = store.get(id)
    if sent := doc.get("emails", {}).get("suggestion"):
        return sent
    simulate("suggest", body.get("simulate"))
    requisition = Requisition.model_validate(doc["requisition"])
    html, text = emails.suggestion(doc["classification"])
    sent = send(
        "suggestion",
        requisition.submitted_by,
        emails.LEKKAI,
        emails.subject(requisition.payable_to, requisition.response_number, doc.get("test")),
        html,
        text,
        body["thread"],
        doc.get("test"),
    )
    store.record(id, emails={"suggestion": email(sent)})
    return sent


@router.post("/post")
def post(id: str, body: dict):
    # "unrecorded" posts, then fails the write that follows
    code = body.get("simulate")
    classification = store.get(id)["classification"]
    posted = mifos.post(id, classification["debit"], classification["credit"], None if code == "unrecorded" else code)
    store.record(id, fail=code == "unrecorded", status="posted", mifos_transaction_id=posted["mifos_transaction_id"])
    return posted


@router.get("/read-back/{mifos_transaction_id}")
def read_back(id: str, mifos_transaction_id: str, code: str | None = Query(None, alias="simulate")):
    # The stub echoes what we posted. Real Mifos will answer from the ledger
    classification = store.get(id)["classification"]
    return mifos.read_back(mifos_transaction_id, classification["debit"], classification["credit"], code)


@router.post("/confirm")
def confirm(id: str, body: dict):
    # Mifos is a stub: an email confirming a post that didn't happen would be a lie (phase 9 ADR 6)
    simulate("confirm", body.get("simulate"))
    log("confirm: no email while Mifos is a stub", mifos_transaction_id=body["mifos_transaction_id"])
    return {"sent": False}


# Needs nothing from the database, so someone still hears when the database is what broke. A form the trigger
# couldn't clean comes here too, with no requisition: only what the form sent
@router.post("/handover")
def handover(id: str, body: dict):
    try:
        if sent := store.get(id).get("emails", {}).get("handover"):
            return sent
    except HTTPException:
        pass  # Sent anyway: someone has to hear
    simulate("handover", body.get("simulate"))
    requisition, raw = body.get("requisition"), body.get("raw") or {}
    if requisition:
        submitter, payable_to, number = (requisition.get(k) for k in ("submitted_by", "payable_to", "response_number"))
    else:
        submitter, payable_to, number = (
            raw.get(k) for k in ("submitter_email_address", "payable_to", "response_number")
        )
    html, text = emails.handover(body["error"], None if requisition else raw)
    sent = send(
        "handover",
        submitter if isinstance(submitter, str) else None,
        emails.LEKKAI,
        emails.subject(payable_to, number, body.get("test")),
        html,
        text,
        body.get("thread"),
        body.get("test"),
    )
    store.record(id, emails={"handover": email(sent)}, **({} if requisition else {"raw": raw}))
    return sent


@router.post("/complete")
def complete(id: str, body: dict):
    ended = {k: body[k] for k in ("status", "reason", "mifos_transaction_id") if body.get(k) is not None}
    store.record(id, **ended, execution={"completed_at": store.NOW})
    return {"status": body["status"]}


def email(sent: dict) -> dict:
    return {"message_id": sent["message_id"], "thread_id": sent["thread_id"], "at": store.NOW}


def send(
    kind: str, submitter: str | None, sender_name: str, subject: str, html: str, text: str, thread=None, test=False
) -> dict:
    to, dropped = emails.recipients(submitter, test)
    sent = gmail_call(gmail.send, to, sender_name, subject, html, text, thread)
    # Counts, not addresses: who it went to is in Gmail
    log(
        f"emailed: {kind}",
        to=len(to),
        dropped=dropped,
        reply=bool(thread),
        test=bool(test),
        message_id=sent["message_id"],
    )
    return sent


def gmail_call(fn, *args):
    """Gmail's retryable statuses pass through for the workflow to retry. Anything else is ours: a 500, handed over"""
    try:
        return fn(*args)
    except WorkspaceError as e:
        raise HTTPException(e.status if e.status in RETRIED else 500, f"gmail: {e}") from e
