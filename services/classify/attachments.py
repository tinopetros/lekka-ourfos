"""A requisition's files, fetched from Drive or our bucket for the model (docs/phase6/tdd.md, docs/phase7/tdd.md)."""

import io

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from common import RETRIED, log
from integrations import gcs
from integrations.workspace import drive
from integrations.workspace.delegation import WorkspaceError
from requisition import Requisition


async def load(requisition: Requisition) -> list[dict]:
    """Every file, in field order, or an HTTPException the workflow retries or hands over. Never a silent drop."""
    files = []
    for field, refs in requisition.files.model_dump().items():
        for ref in refs:
            try:
                got = await run_in_threadpool(fetch, ref)
            except (WorkspaceError, gcs.GcsError) as e:
                # Retryable statuses pass through. Anything else is this file's problem, so a handover
                status = e.status if e.status in RETRIED else 422
                raise HTTPException(status, f"{field} {ref}: cannot fetch, {e}") from e
            files.append(normalize({"field": field} | got))
    check(files)
    log("attachments", count=len(files), bytes=sum(f["size"] for f in files))
    return files


def fetch(ref: str) -> dict:
    """A gs:// ref is our bucket. Anything else is a Drive id, as every requisition before phase 7 has."""
    return gcs.fetch(ref) if ref.startswith("gs://") else drive.fetch(ref)


# What Drive or a browser sometimes calls a type Gemini knows by another name
ALIASES = {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg", "image/x-png": "image/png"}


def normalize(f: dict) -> dict:
    """Any image Pillow reads is shown: types Gemini doesn't take become PNG. Everything else as is.

    Never resized: Gemini scales images to 3072px itself, and bills after, so shrinking first would only lose detail.
    """
    was = f["mimeType"]
    f = f | {"mimeType": ALIASES.get(was, was)}
    if f["mimeType"] in drive.SHOWN:
        return f
    try:
        image = Image.open(io.BytesIO(f["data"]))
        image.load()
    except (UnidentifiedImageError, OSError):
        # Not an image Pillow reads (a .docx, a spreadsheet): check decides
        return f
    out = io.BytesIO()
    image.convert("RGBA").save(out, "PNG")
    data = out.getvalue()
    log("attachment converted", field=f["field"], id=f["id"], was=was, bytes_was=f["size"], bytes=len(data))
    return f | {"mimeType": "image/png", "size": len(data), "data": data}


def check(files: list[dict]):
    """Only what the model can be shown, and not too much of it."""
    for f in files:
        if f["mimeType"] not in drive.SHOWN:
            raise HTTPException(422, f"{f['field']} {f['id']}: {f['mimeType']} can't be shown to the model")
    total = sum(f["size"] for f in files)
    if total > drive.MAX_BYTES:
        raise HTTPException(422, f"attachments are {total} bytes, over {drive.MAX_BYTES}")
