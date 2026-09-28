"""Gmail as lekkai@, a setup check (docs/phase6/adr.md 6). Called by hand with an ID token, never by the workflow."""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

import google_workspace
from common import log

router = APIRouter(prefix="/workspace")


async def call(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except google_workspace.WorkspaceError as e:
        raise HTTPException(e.status, str(e)) from e


@router.get("/messages")
async def messages(subject: str):
    found = await call(google_workspace.messages, subject)
    # Counts and ids only: subjects and addresses stay out of the logs
    log("workspace messages", count=len(found))
    return found


@router.get("/threads/{thread_id}")
async def thread(thread_id: str):
    found = await call(google_workspace.thread, thread_id)
    log("workspace thread", thread_id=thread_id, count=len(found))
    return found


class Email(BaseModel):
    subject: str
    body: str


@router.post("/send")
async def send(email: Email):
    sent = await call(google_workspace.send_to_self, email.subject, email.body)
    log("workspace sent to self", message_id=sent["id"])
    return sent
