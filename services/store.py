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


def claim(form: str, id: str, run: str, given: str | None) -> str:
    """The submission's live entry, for this run to correct, or why not. In one transaction,
    so two corrections can't both reverse it. A retry of the same run gets the entry it already claimed."""
    parent = submission(form, id).ref
    try:
        return _claim(client().transaction(), parent, run, given)
    except exceptions.GoogleAPICallError as e:
        raise _status(e) from e


@firestore.transactional
def _claim(transaction, parent, run, given):
    doc = parent.get(transaction=transaction).to_dict() or {}
    held = doc.get("claim") or {}
    other = None
    if held.get("run") and held["run"] != run:
        other = parent.collection("runs").document(held["run"]).get(transaction=transaction).to_dict() or {}
    entry = claimable(doc, other, run, given)
    transaction.set(parent, {"claim": {"run": run, "entry": entry}, "updated_at": NOW}, merge=True)
    return entry


def claimable(doc: dict, other: dict | None, run: str, given: str | None) -> str:
    """Which entry a correction may reverse. other is the run holding the claim, when it isn't this one.

    A claim stands until its run ends without having tried the mirror. One that tried and didn't hear back stands for
    good: only a person checking Mifos can say whether it landed."""
    held = doc.get("claim") or {}
    if held.get("run") == run:
        return held["entry"]
    if other is not None:
        if other.get("status") not in ENDED:
            raise HTTPException(409, f"Correction run {held['run']} is still correcting it")
        reversal = other.get("reversal") or {}
        if reversal.get("tried") and not reversal.get("transaction_id"):
            raise HTTPException(
                409,
                f"Correction run {held['run']} may have reversed {held['entry']} without hearing back. "
                "Check Mifos before correcting it again",
            )
    live = doc.get("live_entry")
    if not live:
        raise HTTPException(409, "Nothing posted to correct")
    if given and given != live:
        raise HTTPException(409, f"Transaction {given} isn't this requisition's live entry, {live} is")
    return live


# How a run ended is final. A step that answers after the workflow gave up on it, like a slow post, still records
# what it did but can't move the status back. A status that stands is the submission's too, so a list needs one read
@firestore.transactional
def _save_status(transaction, ref, parent, fields):
    if (ref.get(transaction=transaction).to_dict() or {}).get("status") in ENDED:
        fields = {k: v for k, v in fields.items() if k != "status"}
    transaction.set(ref, fields, merge=True)
    # A refused correction changed nothing, so the submission's status stands
    if fields.get("status") not in (None, "refused"):
        transaction.set(parent, {"status": fields["status"], "run": ref.id, "updated_at": NOW}, merge=True)


ENDED = {"done", "rejected", "handed_over", "failed", "refused"}


def _status(e: exceptions.GoogleAPICallError) -> HTTPException:
    # What the workflow retries passes through (is_transient), anything else hands over
    return HTTPException(e.code if e.code in RETRIED else 500, f"firestore: {e.code}")
