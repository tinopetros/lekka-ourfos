import os
from functools import cache

from fastapi import HTTPException
from google.api_core import exceptions
from google.cloud import firestore

from common import RETRIED, log
from forms import FORMS

NOW = firestore.SERVER_TIMESTAMP


@cache
def client():
    return firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "ourfos"))


def submission(form: str, id: str) -> "Doc":
    """What was submitted, once, and its thread (docs/phase10/adr.md 3)."""
    return Doc(client().collection(FORMS[form].collection).document(id))


def run(form: str, id: str, run: str) -> "Doc":
    """One workflow run on a submission, named by its execution id: what it did, and how it ended."""
    parent = submission(form, id).ref
    return Doc(parent.collection("runs").document(run), parent)


class Doc:
    def __init__(self, ref, parent=None):
        self.ref, self.parent = ref, parent

    def get(self) -> dict:
        try:
            doc = self.ref.get()
        except exceptions.GoogleAPICallError as e:
            raise _status(e) from e
        if not doc.exists:
            raise HTTPException(404, f"no {self.ref.path}")
        return doc.to_dict()

    def save(self, **fields):
        """A merge, so a retried step writes the same thing twice and nothing more."""
        try:
            if "status" in fields and self.parent:
                _save_status(client().transaction(), self.ref, self.parent, fields | {"updated_at": NOW})
            else:
                self.ref.set(fields | {"updated_at": NOW}, merge=True)
        except exceptions.GoogleAPICallError as e:
            raise _status(e) from e

    def record(self, fail: bool = False, **fields):
        """save, after a side effect: a failure is logged, never raised, since what happened already happened."""
        try:
            if fail:
                raise HTTPException(503, "simulated unrecorded")
            self.save(**fields)
        except Exception as e:  # noqa: BLE001  anything at all: the step already happened
            log(f"not recorded: {e}", "ERROR", fields=sorted(fields))


# How a run ended is final. A step that answers after the workflow gave up on it, like a slow post, still records
# what it did but can't move the status back. A status that stands is the submission's too, so a list needs one read
@firestore.transactional
def _save_status(transaction, ref, parent, fields):
    if (ref.get(transaction=transaction).to_dict() or {}).get("status") in ENDED:
        fields = {k: v for k, v in fields.items() if k != "status"}
    transaction.set(ref, fields, merge=True)
    if "status" in fields:
        transaction.set(parent, {"status": fields["status"], "run": ref.id, "updated_at": NOW}, merge=True)


ENDED = {"done", "rejected", "handed_over", "failed"}


def _status(e: exceptions.GoogleAPICallError) -> HTTPException:
    # What the workflow retries passes through (is_transient), anything else hands over
    return HTTPException(e.code if e.code in RETRIED else 500, f"firestore: {e.code}")
