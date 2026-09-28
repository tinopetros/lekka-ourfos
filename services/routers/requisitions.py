"""The requisition workflow's one service. It owns the requisition's document and calls everything else for it."""

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

import expenser_runner
import mifos
import store
import workspace
from common import log, simulate
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
        # "stub", or a forced failure. In a thread, so a simulated hang can't block the event loop
        await run_in_threadpool(simulate, "classify", code)
        classification = stub(amount, code)
    else:
        classification = await expenser_runner.classify(requisition)

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


# The handover path goes through here too, so the thread is recorded, never required
@router.get("/thread")
def thread(id: str, response_number: int, code: str | None = Query(None, alias="simulate")):
    found = workspace.get_thread(response_number, code)
    store.record(id, thread_id=found["thread_id"])
    return found


@router.post("/notify")
def notify(id: str, body: dict):
    classification = store.get(id)["classification"]
    sent = workspace.notify(body["thread_id"], "classification", classification, body.get("simulate"))
    store.record(id, emails={"classification": email(sent)})
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
    confirmation = {"mifos_transaction_id": body["mifos_transaction_id"]}
    sent = workspace.notify(body["thread_id"], "confirmation", confirmation, body.get("simulate"))
    store.record(id, emails={"confirmation": email(sent)})
    return sent


# Needs nothing from the database, so someone still hears when the database is what broke
@router.post("/handover")
def handover(id: str, body: dict):
    sent = workspace.notify(body["thread_id"], "error", body["error"], body.get("simulate"))
    store.record(id, emails={"handover": email(sent)})
    return sent


@router.post("/complete")
def complete(id: str, body: dict):
    ended = {k: body[k] for k in ("status", "reason", "mifos_transaction_id") if body.get(k) is not None}
    store.record(id, **ended, execution={"completed_at": store.NOW})
    return {"status": body["status"]}


def email(sent: dict) -> dict:
    return {"message_id": sent["message_id"], "at": store.NOW}
