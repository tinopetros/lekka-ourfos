"""A submission from our own form: checked, numbered and stored in one transaction, then its workflow started with
its argument. Submitting again is safe: it answers with what was submitted the first time."""

import os
from datetime import UTC, datetime

from fastapi import HTTPException
from google.cloud.firestore import SERVER_TIMESTAMP, Query, transactional
from pydantic import BaseModel, ValidationError

import store
from common import log
from forms import FORMS
from integrations import workflows

from . import drafts

COUNTERS = "counters"


# Pydantic's words for what the form says itself, so the two read the same (web/src/features/forms/schema.ts)
SAID = {
    "missing": "Required",
    "string_too_short": "Required",
    "too_short": "Add at least one file",
    "multiple_of": "To the cent: at most 2 decimal places",
    "literal_error": "Choose one of the options",
}


def said(err: dict) -> str:
    """In the form's words, where it has them. A pattern's, by what it asks for: a link, or an account number."""
    if err["type"] == "string_pattern_mismatch":
        pattern = (err.get("ctx") or {}).get("pattern", "")
        return "Up to 9 digits, e.g. 428 or 000000428" if "\\d{9}" in pattern else "That's not the link it asks for"
    return SAID.get(err["type"], err["msg"].removeprefix("Value error, "))


def problems(error: ValidationError) -> list[dict]:
    """Each problem by its field, for the form to show by it, in the form's own words where it has them."""
    return [{"loc": list(err["loc"]), "msg": said(err)} for err in error.errors()]


def check(form: str, answers: dict) -> BaseModel:
    """The form's own model, strict."""
    try:
        return FORMS[form].model.model_validate(answers)
    except ValidationError as e:
        raise HTTPException(422, problems(e)) from e


def look_over(form: str, answers: dict) -> list[dict]:
    """What submitting these answers would find wrong, without refusing them: a draft's, as it's saved."""
    try:
        FORMS[form].model.model_validate(answers)
    except ValidationError as e:
        return problems(e)
    return []


def counts_up() -> bool:
    # Prod's numbers carry on from its Google Forms'. Anywhere else they're below zero, plain to see in an inbox
    return os.environ.get("ENVIRONMENT") == "prod"


def counter_of(form: str, test: bool, up: bool) -> tuple[str, bool]:
    """Which count a submission takes its number from, and which way it goes. On prod a test has a count of its own,
    below zero: it never takes a number a form's Google Form, still open while ours is tried, will also give out.
    Elsewhere every number is below zero already, so tests and the rest share one count."""
    if up and test:
        return f"{form}-test", False
    return form, up


def first(numbers: list[int], up: bool) -> int:
    """Past the furthest number a form has, on its side of zero."""
    return max([0, *numbers]) + 1 if up else min([0, *numbers]) - 1


def seed(tx, collection, up: bool) -> int:
    """A form's first number from ourfos, when it has no counter yet: one past the highest it has on prod, carrying on
    from its Google Form's, or below the lowest elsewhere. No seeding script."""
    direction = Query.DESCENDING if up else Query.ASCENDING
    last = collection.order_by("response_number", direction=direction).limit(1).get(transaction=tx)
    return first([d.to_dict()["response_number"] for d in last], up)


def record(tx, form: str, id: str, answers: BaseModel, user: str, test: bool) -> dict:
    """The submission as stored: the one there already, if it was submitted, or a new one, numbered. Every read
    before any write, as a transaction must."""
    spec, db = FORMS[form], store.client()
    name, up = counter_of(form, test, counts_up())
    collection = db.collection(spec.collection)
    ref, counter = collection.document(id), db.collection(COUNTERS).document(name)
    doc = ref.get(transaction=tx).to_dict()
    if doc and doc.get("submitted_by") != user:
        raise HTTPException(409, f"{id} is someone else's")
    if doc and doc.get("status") != "draft":
        return doc
    count = counter.get(transaction=tx).to_dict()
    number = count["next"] if count else seed(tx, collection, up)

    now = datetime.now(UTC)
    identity = {"response_number": number, "response_id": id, "submitted_by": user, "submitted_at": now}
    submission = spec.submission.model_validate(answers.model_dump() | identity | {"source": "ourfos"})
    doc = identity | {
        "form": form,
        "source": "ourfos",
        "answers": submission.to_firestore(),
        "test": test,
        "status": "received",
        "received_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    }
    tx.set(counter, {"next": number + (1 if up else -1)})
    tx.set(ref, doc)
    return doc


def submit(form: str, id: str, answers: dict, test: bool, user: str) -> dict:
    spec, checked = FORMS[form], check(form, answers)
    drafts.check_files(form, id, checked.model_dump())
    doc = transactional(record)(store.client().transaction(), form, id, checked, user, test)
    if not doc.get("execution_id"):
        # Again, if starting it failed last time, with posting as this environment has it
        submission = spec.submission.model_validate(doc["answers"])
        argument = {
            "form": form,
            "id": id,
            "submission": submission.to_json(),
            "test": bool(doc.get("test")),
            "mifos": os.environ.get("POST_TO_MIFOS") == "true",
        }
        execution_id = workflows.start(spec.workflow, argument)
        store.submission(form, id).save(execution_id=execution_id)
        log("submitted", form=form, response_number=submission.response_number, execution_id=execution_id, test=test)
    return doc
