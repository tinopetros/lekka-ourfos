"""Gmail, stubbed. Dicts in and out, failures as HTTP statuses, so it can move behind a network hop unchanged."""

from fastapi import HTTPException

from common import log, simulate


def get_thread(response_number: int, code=None) -> dict:
    if code == "missing":
        log("simulating thread missing", "WARNING", step="get_thread")
        raise HTTPException(404, "thread missing")
    simulate("get_thread", code)
    log("get_thread", response_number=response_number)
    return {"thread_id": f"stub-thread-{response_number}"}


def notify(thread_id: str, kind: str, content, code=None) -> dict:
    """One call, three kinds of email: classification, confirmation or error."""
    simulate("notify", code)
    log(f"notify: {kind}", thread_id=thread_id, **{kind: content})
    return {"message_id": f"stub-message-{kind}", "thread_id": thread_id}
