from fastapi import APIRouter, HTTPException, Query, Request

from common import log, simulate

router = APIRouter(prefix="/workspace/gmail")


@router.get("/thread")
def get_thread(request: Request, response_number: int, code: str | None = Query(None, alias="simulate")):
    if code == "missing":
        log(request, "simulating thread missing", "WARNING", step="get_thread")
        raise HTTPException(404, "thread missing")
    simulate(request, "get_thread", code)
    log(request, "get_thread", response_number=response_number)
    return {"thread_id": f"stub-thread-{response_number}"}


@router.post("/notify/thread/{thread_id}")
def notify(request: Request, thread_id: str, body: dict):
    simulate(request, "notify", body.get("simulate"))
    # One endpoint, three kinds of email: whichever key is present decides
    kind = next(k for k in ("error", "classification", "confirmation") if k in body)
    log(request, f"notify: {kind}", thread_id=thread_id, **{kind: body[kind]})
    return {"message_id": f"stub-message-{kind}", "thread_id": thread_id}
