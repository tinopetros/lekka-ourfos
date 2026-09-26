import os
from functools import cache

from fastapi import HTTPException
from google.api_core import exceptions
from google.cloud import firestore

from common import RETRIED, log

NOW = firestore.SERVER_TIMESTAMP


@cache
def client():
    return firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "ourfos"))


def requisitions():
    return client().collection("requisitions")


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
    ref = requisitions().document(id)
    try:
        if "status" in fields:
            _save_status(client().transaction(), ref, fields | {"updated_at": NOW})
        else:
            ref.set(fields | {"updated_at": NOW}, merge=True)
    except exceptions.GoogleAPICallError as e:
        raise _status(e) from e


# How a run ended is final. A step that answers after the workflow gave up on it,
# like a slow post, still records what it did but can't move the status back
@firestore.transactional
def _save_status(transaction, ref, fields):
    if (ref.get(transaction=transaction).to_dict() or {}).get("status") in ENDED:
        fields = {k: v for k, v in fields.items() if k != "status"}
    transaction.set(ref, fields, merge=True)


ENDED = {"done", "rejected", "handed_over", "failed"}


def record(id: str, fail: bool = False, **fields):
    """save, after a side effect: a failure is logged, never raised, since what happened already happened."""
    try:
        if fail:
            raise HTTPException(503, "simulated unrecorded")
        save(id, **fields)
    except Exception as e:  # noqa: BLE001  anything at all: the step already happened
        log(f"not recorded: {e}", "ERROR", fields=sorted(fields))


def _status(e: exceptions.GoogleAPICallError) -> HTTPException:
    # What the workflow retries passes through (is_transient), anything else hands over
    return HTTPException(e.code if e.code in RETRIED else 500, f"firestore: {e.code}")
