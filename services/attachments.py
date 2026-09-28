"""A requisition's files, fetched from Drive for the model (docs/phase6/tdd.md, Attachments into classify)."""

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

import google_workspace
from common import RETRIED, log
from requisition import Requisition


async def load(requisition: Requisition) -> list[dict]:
    """Every file, in field order, or an HTTPException the workflow retries or hands over. Never a silent drop."""
    files = []
    for field, ids in requisition.files.model_dump().items():
        for file_id in ids:
            try:
                got = await run_in_threadpool(google_workspace.fetch, file_id)
            except google_workspace.WorkspaceError as e:
                # Drive's retryable statuses pass through. Anything else is this file's problem, so a handover
                status = e.status if e.status in RETRIED else 422
                raise HTTPException(status, f"{field} {file_id}: cannot fetch, {e}") from e
            files.append({"field": field} | got)
    check(files)
    log("attachments", count=len(files), bytes=sum(f["size"] for f in files))
    return files


def check(files: list[dict]):
    """Only what the model can be shown, and not too much of it."""
    for f in files:
        if f["mimeType"] not in google_workspace.SHOWN:
            raise HTTPException(422, f"{f['field']} {f['id']}: {f['mimeType']} can't be shown to the model")
    total = sum(f["size"] for f in files)
    if total > google_workspace.MAX_BYTES:
        raise HTTPException(422, f"attachments are {total} bytes, over {google_workspace.MAX_BYTES}")


def seen(files: list[dict]) -> list[dict]:
    """What the document keeps: never the bytes."""
    return [{k: f[k] for k in ("field", "id", "name", "mimeType", "size")} for f in files]
