"""What every form's workflow does: receive, acknowledge, hand over, complete (docs/phase10/tdd.md).

The path names the submission. The run is the execution id call_service sends in X-Execution-Id.
"""

from fastapi import APIRouter, HTTPException

import emails
import store
from common import RETRIED, execution_id, log, simulate,
from forms import FORMS
from integrations.workspace import gmail
from integrations.workspace.delegation import WorkspaceError

router = APIRouter(prefix="/forms/{form}/{id}")


def run_id() -> str:
    if not (run := execution_id.get()):
        raise HTTPException(400, "X-Execution-Id names the run")
    return run


def known(form: str):
    if form not in FORMS:
        raise HTTPException(404, f"no form {form}")


@router.post("")
def receive(form: str, id: str, body: dict):
    known(form)
    submission = FORMS[form].model.model_validate(body["submission"])
    test = bool(body.get("test"))
    store.submission(form, id).save(
        form=form,
        answers=submission.to_firestore(),
        raw=body.get("raw"),
        test=test,
        response_number=submission.response_number,
        submitted_by=submission.submitted_by,
        submitted_at=submission.submitted_at,
    )
    # Only ever set on dev: the prod workflow drops it
    simulate = {"simulate": body["simulate"]} if body.get("simulate") else {}
    store.run(form, id, run_id()).save(
        **simulate,
        workflow=body.get("workflow"),
        test=test,
        status="received",
        execution={"started_at": store.NOW, "revision": body.get("revision")},
    )
    log("received", form=form, response_number=submission.response_number)
    return {"status": "received"}


@router.post("/acknowledge")
def acknowledge(form: str, id: str, body: dict):
    """The first email, which starts the thread every other email replies in. Once a submission, whichever run"""
    known(form)
    doc = store.submission(form, id).get()
    if thread := doc.get("thread"):
        return thread
    sent = doc.get("emails", {}).get("acknowledgement")
    if not sent:
        simulate("acknowledge", body.get("simulate"))
        submission = FORMS[form].model.model_validate(doc["answers"])
        test = doc.get("test")
        html, text = emails.acknowledgement(form, submission)
        sent = send(
            form,
            "acknowledgement",
            submission.submitted_by,
            emails.form_name(form),
            emails.subject(form, emails.names(form, doc["answers"]), submission.response_number, test),
            html,
            text,
            test=test,
        )
        store.submission(form, id).record(emails={"acknowledgement": email(sent)})
    # Its Message-ID too, so replies thread in any client. Read after the send is recorded: a retry never resends
    thread = {"thread_id": sent["thread_id"], "in_reply_to": gmail_call(gmail.rfc822_id, sent["message_id"])}
    store.submission(form, id).record(thread=thread)
    return thread


# Needs nothing from the database, so someone still hears when the database is what broke. A form the trigger
# couldn't clean comes here too, with no submission: only what the form sent
@router.post("/handover")
def handover(form: str, id: str, body: dict):
    known(form)
    run = store.run(form, id, run_id())
    try:
        if sent := run.get().get("emails", {}).get("handover"):
            return sent
    except HTTPException:
        pass  # Sent anyway: someone has to hear
    simulate("handover", body.get("simulate"))
    submission, raw, test = body.get("submission"), body.get("raw") or {}, body.get("test")
    # A form's subject keys are the webhook's own, so raw names them too
    answers = submission or raw
    submitter = answers.get("submitted_by" if submission else "submitter_email_address")
    html, text = emails.handover(form, body["error"], None if submission else raw)
    sent = send(
        form,
        "handover",
        submitter if isinstance(submitter, str) else None,
        emails.LEKKAI,
        emails.subject(form, emails.names(form, answers), answers.get("response_number"), test),
        html,
        text,
        body.get("thread"),
        test,
    )
    run.record(emails={"handover": email(sent)})
    if not submission:
        store.submission(form, id).record(form=form, raw=raw, test=bool(test))
    return sent


@router.post("/complete")
def complete(form: str, id: str, body: dict):
    known(form)
    ended = {k: body[k] for k in ("status", "reason", "mifos_transaction_id", "workflow") if body.get(k) is not None}
    store.run(form, id, run_id()).record(**ended, execution={"completed_at": store.NOW})
    return {"status": body["status"]}


def email(sent: dict) -> dict:
    return {"message_id": sent["message_id"], "thread_id": sent["thread_id"], "at": store.NOW}


def send(
    form: str,
    kind: str,
    submitter: str | None,
    sender_name: str,
    subject: str,
    html: str,
    text: str,
    thread=None,
    test=False,
) -> dict:
    to, dropped = emails.recipients(form, submitter, test)
    sent = gmail_call(gmail.send, to, sender_name, subject, html, text, thread, emails.reply_to(form, test))
    # Counts, not addresses: who it went to is in Gmail
    log(
        f"emailed: {kind}",
        form=form,
        to=len(to),
        dropped=dropped,
        reply=bool(thread),
        test=bool(test),
        message_id=sent["message_id"],
    )
    return sent


def gmail_call(fn, *args):
    """Gmail's retryable statuses pass through for the workflow to retry. Anything else is ours: a 500, handed over"""
    try:
        return fn(*args)
    except WorkspaceError as e:
        raise HTTPException(e.status if e.status in RETRIED else 500, f"gmail: {e}") from e
