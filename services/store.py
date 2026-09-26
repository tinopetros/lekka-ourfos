import os
from functools import cache

from fastapi import HTTPException
from google.api_core import exceptions
from google.cloud import firestore

from common import log

NOW = firestore.SERVER_TIMESTAMP


@cache
def requisitions():
    return firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "ourfos")).collection("requisitions")


def get(id: str) -> dict:
    try:
        doc = requisitions().document(id).get()
    except exceptions.GoogleAPICallError as e:
        raise _status(e) from e
    if not doc.exists:
        raise HTTPException(404, f"no requisition {id}")
    return doc.to_dict()


def save(id: str, **fields):
    """A merge, so a retried step writes the same thing twice and nothing more."""
    try:
        requisitions().document(id).set(fields | {"updated_at": NOW}, merge=True)
    except exceptions.GoogleAPICallError as e:
        raise _status(e) from e


def record(id: str, fail: bool = False, **fields):
    """save, after a side effect: a failure is logged, never raised, since what happened already happened."""
    try:
        if fail:
            raise HTTPException(503, "simulated unrecorded")
        save(id, **fields)
    except Exception as e:  # noqa: BLE001  anything at all: the step already happened
        log(f"not recorded: {e}", "ERROR", fields=sorted(fields))


def _status(e: exceptions.GoogleAPICallError) -> HTTPException:
    # 429 and 503 are retried by the workflow, anything else hands over
    return HTTPException(e.code if e.code in (429, 503) else 500, f"firestore: {e.code}")
