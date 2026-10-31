"""What a person does to a submission from the UI, beside its workflows: approves or closes it, or comments. The thread hears first, and the action is kept only once it has, so nothing is recorded that nobody was told.

The run is the action's workflow execution, which names the action too: actions/{run}.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

import emails
import store
from common import log
from journal import HARARE
from routers.forms import email, known, run_id, send

router = APIRouter(prefix="/forms/{form}/{id}/action")

# Each kind, and the status it leaves the submission in: a comment leaves it as it was
KINDS = {"approve": "approved", "close": "closed", "comment": None}
# An approval may go without a word; anything else says why
QUIET = {"approve"}


def asked(body: dict) -> tuple[str, str, str]:
    kind, by, comment = body.get("kind"), (body.get("by") or "").strip(), (body.get("comment") or "").strip()
    if kind not in KINDS:
        raise HTTPException(422, f"No action {kind}")
    if not by or not (comment or kind in QUIET):
        raise HTTPException(422, "An action needs who did it and a comment")
    return kind, by, comment


@router.post("/email")
def tell(form: str, id: str, body: dict):
    """The reply in the submission's thread"""
    known(form)
    submission = store.submission(form, id).get()
    answers, test = submission.get("answers") or {}, submission.get("test")
    at = f"{datetime.now(HARARE):%d %b %Y, %H:%M} CAT"
    kind, by, comment = asked(body)
    html, text = emails.acted(
        kind, form, id, body.get("by_name") or by, comment, body.get("files") or [], at, body.get("reversal")
    )
    submitter = answers.get("submitted_by")
    return send(
        form,
        kind,
        submitter if isinstance(submitter, str) else None,
        emails.LEKKAI,
        emails.subject(form, emails.names(form, answers), answers.get("response_number"), test),
        html,
        text,
        submission.get("thread"),
        test,
    )


@router.post("/record")
def record(form: str, id: str, body: dict):
    """The action, once its email went: kept under the submission, and its status set. A retry writes the same"""
    known(form)
    kind, by, comment = asked(body)
    run = run_id()
    store.action(form, id, run).save(
        kind=kind,
        by=by,
        comment=comment,
        files=body.get("files") or [],
        at=store.NOW,
        email=email(body["email"]) if body.get("email") else None,
    )
    if status := KINDS[kind]:
        store.submission(form, id).save(status=status, action=run)
    log("action recorded", kind=kind, form=form, action=run)
    return {"status": kind}
