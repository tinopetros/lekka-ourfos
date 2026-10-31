import itertools
import os
import re
import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from google.cloud import firestore

import store
from common import log
from forms import FORMS
from integrations import gcs, services, workflows
from submission import ID

from . import drafts, people, views
from . import submit as submitting
from .auth import current_user
from .models import (
    Account,
    Acting,
    Action,
    ActionRequest,
    ActionState,
    CorrectRequest,
    Draft,
    DraftRequest,
    FormInfo,
    JournalEntry,
    JournalEntryPage,
    Me,
    Person,
    ReverseRequest,
    Reversing,
    Submission,
    SubmissionPage,
    SubmitRequest,
    Submitted,
    Uploaded,
)
from .permissions import allowed, granted, needs

# Each route's operation named by its function: the generated TypeScript's names
router = APIRouter(prefix="/api", generate_unique_id_function=lambda route: route.name)
# journal.py's, not imported: it brings the Mifos connector, and Mifos is ourfos-services' alone
JOURNAL = "journal_entries"
User = Annotated[str, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=100)]


def known(form: str):
    if form not in FORMS:
        raise HTTPException(404, f"No form {form}")


def page(collection, field: str, cursor: str | None, limit: int, keep=None):
    """Newest first, cursor paginated. The cursor is the last document's id: the next page starts after it. One more
    than asked for says whether there's a next page. keep, if given, picks from each batch read the documents to show:
    read on until there are enough, so a page is full however many it leaves out."""
    query = collection.order_by(field, direction=firestore.Query.DESCENDING)
    if cursor:
        after = collection.document(cursor).get()
        if not after.exists:
            raise HTTPException(400, "That page is gone: start again")
        query = query.start_after(after)
    if keep is None:
        docs = list(query.limit(limit + 1).stream())
    else:
        docs = []
        for batch in itertools.batched(query.stream(), limit + 1):
            docs += keep(list(batch))
            if len(docs) > limit:
                break
    return docs[:limit], docs[limit - 1].id if len(docs) > limit else None


def shows_tests(user: str, permission: str, tests: bool) -> bool:
    """Tests are left out of a list unless asked for, by someone who may make them"""
    if tests and not allowed(user, permission):
        raise HTTPException(403, f"You don't have {permission}")
    return tests


def no_tests(docs):
    return [d for d in docs if not (d.to_dict() or {}).get("test")]


def test_entries(docs) -> set[str]:
    """Which are tests: an entry recorded before entries said so is one if its submission is"""
    data = {d.id: d.to_dict() or {} for d in docs}
    unsaid = [e for e in data.values() if "test" not in e and e.get("form") in FORMS and e.get("submission")]
    refs = [store.client().collection(FORMS[e["form"]].collection).document(e["submission"]) for e in unsaid]
    tests = {s.id for s in store.client().get_all(refs) if s.exists and s.to_dict().get("test")} if refs else set()
    return {id for id, e in data.items() if e.get("test") or e.get("submission") in tests}


def no_test_entries(docs):
    tests = test_entries(docs)
    return [d for d in docs if d.id not in tests]


@router.get("/me")
def me(email: User) -> Me:
    return Me(
        email=email,
        name=people.name(email),
        environment=os.environ.get("ENVIRONMENT", "local"),
        version=os.environ.get("VERSION", "local"),
        permissions=granted(email),
    )


@router.get("/people/{email}")
def person(email: str, _: User) -> Person:
    return Person(email=email, name=people.name(email))


@router.get("/forms")
def forms(_: User) -> list[FormInfo]:
    return [FormInfo(key=form, title=spec.title, tracks_status=spec.tracks_status) for form, spec in FORMS.items()]


@router.get("/forms/{form}/submissions")
def submissions(
    form: str,
    user: Annotated[str, needs("forms:{form}:read")],
    cursor: str | None = None,
    limit: Limit = 25,
    tests: bool = False,
) -> SubmissionPage:
    known(form)
    collection = store.client().collection(FORMS[form].collection)
    keep = None if shows_tests(user, f"forms:{form}:test", tests) else no_tests
    docs, next = page(collection, "received_at", cursor, limit, keep)
    return SubmissionPage(items=[views.summary(form, d.id, d.to_dict()) for d in docs], next=next)


@router.get("/forms/{form}/submissions/{id}")
def submission(form: str, id: str, user: Annotated[str, needs("forms:{form}:read")]) -> Submission:
    known(form)
    ref = store.client().collection(FORMS[form].collection).document(id)
    doc = ref.get()
    data = doc.to_dict() if doc.exists else None
    # Someone else's draft is as good as not there
    if data is None or (data.get("status") == drafts.DRAFT and data.get("submitted_by") != user):
        raise HTTPException(404, f"No {FORMS[form].noun} {id}")
    runs = [views.run(r.id, r.to_dict()) for r in ref.collection("runs").stream()]
    ids = data.get("journal_entries") or []
    refs = [store.client().collection(JOURNAL).document(i) for i in ids]
    entries = {e.id: e for e in store.client().get_all(refs) if e.exists}
    actions = [Action(id=a.id, **a.to_dict()) for a in ref.collection("actions").stream()]
    return views.submission(
        form, id, data, runs, [views.journal_entry(i, entries[i].to_dict()) for i in ids if i in entries], actions
    )


@router.put("/forms/{form}/submissions/{id}")
def save_draft(form: str, id: str, body: DraftRequest, user: Annotated[str, needs("forms:{form}:submit")]) -> Draft:
    """A draft, saved whole as it's filled in, and looked over as the submit would, so what's wrong shows as you go.
    Refused once it's submitted, or if it's someone else's"""
    known(form)
    if not ID.match(id):
        raise HTTPException(400, "Not an id we can store")
    if body.test and not allowed(user, f"forms:{form}:test"):
        raise HTTPException(403, f"You don't have forms:{form}:test")
    drafts.save(form, id, body.values, body.test, user)
    found = [] if body.answers is None else submitting.look_over(form, body.answers)
    return Draft(id=id, title=drafts.title(form, body.values), problems=found)


@router.delete("/forms/{form}/submissions/{id}", status_code=204)
def discard_draft(form: str, id: str, user: Annotated[str, needs("forms:{form}:submit")]) -> None:
    """A draft, and its files, gone"""
    known(form)
    drafts.discard(form, id, user)


@router.post(
    "/forms/{form}/submissions/{id}/files",
    openapi_extra={"requestBody": {"content": {"application/octet-stream": {"schema": {"type": "string"}}}}},
)
async def upload_file(
    form: str, id: str, name: str, request: Request, user: Annotated[str, needs("forms:{form}:submit")]
) -> Uploaded:
    """A file for a draft, its bytes the body, its name the query: stored under the draft, its gs:// ref back"""
    known(form)
    if not ID.match(id):
        raise HTTPException(400, "Not an id we can store")
    if int(request.headers.get("content-length") or 0) > drafts.MAX_FILE:
        raise HTTPException(413, "Files of up to 25 MB")
    data = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    ref = await run_in_threadpool(drafts.upload, form, id, name, data, content_type, user)
    return Uploaded(ref=ref)


@router.post(
    "/forms/{form}/submissions/{id}/actions/files",
    openapi_extra={"requestBody": {"content": {"application/octet-stream": {"schema": {"type": "string"}}}}},
)
async def upload_action_file(form: str, id: str, name: str, request: Request, user: User) -> Uploaded:
    """A file for an action, before it's taken: stored under the submission's actions, its gs:// ref back. For
    whoever may take one on this form"""
    known(form)
    if not any(allowed(user, f"forms:{form}:{p}") for p, _, _ in ACTIONS.values()):
        raise HTTPException(403, f"You may take no action on {form}")
    if not ID.match(id):
        raise HTTPException(400, "Not an id we can store")
    if int(request.headers.get("content-length") or 0) > drafts.MAX_FILE:
        raise HTTPException(413, "Files of up to 25 MB")
    data = await request.body()
    if not data:
        raise HTTPException(400, "An empty file")
    extension = match.group(0).lower() if (match := drafts.EXTENSION.search(name)) else ""
    content_type = request.headers.get("content-type") or "application/octet-stream"
    ref = await run_in_threadpool(
        gcs.upload, f"{drafts.prefix(form, id)}actions/{uuid.uuid4().hex[:8]}{extension}", data, content_type
    )
    return Uploaded(ref=ref)


# Each action's permission, the statuses it may be taken from (any but a draft, if None), and whether it needs a
# comment. Who holds each, per form, is the policy's: a requisition is disapproved, never approved
ACTIONS = {
    "done": ("resolve", {"handed_over"}, True),
    "approve": ("approve", None, False),
    "disapprove": ("disapprove", None, True),
    "comment": ("comment", None, True),
}
# Decided: not approved or disapproved again
DECIDED = {"approved", "disapproved"}


@router.post("/forms/{form}/submissions/{id}/actions")
def act(form: str, id: str, body: ActionRequest, user: User) -> Acting:
    """Something done to a submission by a person: its thread is told, then it's kept, through the action workflow.
    Only its own files can go with it"""
    known(form)
    permission, statuses, worded = ACTIONS[body.kind]
    if not allowed(user, f"forms:{form}:{permission}"):
        raise HTTPException(403, f"You don't have forms:{form}:{permission}")
    comment = body.comment.strip()
    if worded and not comment:
        raise HTTPException(422, "Say why, in a comment")
    doc = store.client().collection(FORMS[form].collection).document(id).get()
    status = (doc.to_dict() or {}).get("status") if doc.exists else None
    if not doc.exists or status == drafts.DRAFT:
        raise HTTPException(404, f"No {FORMS[form].noun} {id}")
    if statuses is not None and status not in statuses:
        raise HTTPException(409, f"Only a handed-over {FORMS[form].noun} is marked done")
    if body.kind in ("approve", "disapprove") and status in DECIDED:
        raise HTTPException(409, f"This {FORMS[form].noun} is already {status}")
    own = f"gs://{os.environ.get('ATTACHMENTS_BUCKET')}/{drafts.prefix(form, id)}actions/"
    if any(not f.startswith(own) or "/" in f.removeprefix(own) for f in body.files):
        raise HTTPException(422, "Only files uploaded for this action")
    # A requisition disapproved has its live entry reversed first, if it has one
    live = (doc.to_dict() or {}).get("live_entry") if form == "requisition" and body.kind == "disapprove" else None
    argument = {
        "form": form,
        "id": id,
        "kind": body.kind,
        **({"transaction_id": live} if live else {}),
        "by": user,
        "by_name": people.name(user),
        "comment": comment,
        "files": body.files,
    }
    run = workflows.start("action", argument)
    log("action asked", kind=body.kind, form=form, id=id, run=run)
    return Acting(run=run)


@router.get("/forms/{form}/submissions/{id}/actions/{run}")
def action_state(form: str, id: str, run: str, _: Annotated[str, needs("forms:{form}:read")]) -> ActionState:
    """Done once it's recorded; failed, and why, if its run failed before it was"""
    known(form)
    ref = store.client().collection(FORMS[form].collection).document(id).collection("actions").document(run)
    if ref.get().exists:
        return ActionState(state="done")
    state, reason = workflows.state("action", run)
    if state in ("FAILED", "CANCELLED"):
        return ActionState(state="failed", reason=reason or state.lower())
    return ActionState(state="running")


@router.get("/forms/{form}/drafts")
def my_drafts(form: str, user: Annotated[str, needs("forms:{form}:submit")]) -> list[Draft]:
    """Yours, the latest first"""
    known(form)
    return [
        Draft(id=id, title=drafts.title(form, doc.get("draft") or {}), updated_at=doc.get("updated_at"))
        for id, doc in drafts.list_mine(form, user)
    ]


@router.post("/forms/{form}/submissions/{id}/submit")
def submit(form: str, id: str, body: SubmitRequest, user: Annotated[str, needs("forms:{form}:submit")]) -> Submitted:
    """Our own form's submission, under the id the browser made for it: submitting it twice is submitting it once"""
    known(form)
    if not ID.match(id):
        raise HTTPException(400, "Not an id we can store")
    if body.test and not allowed(user, f"forms:{form}:test"):
        raise HTTPException(403, f"You don't have forms:{form}:test")
    doc = submitting.submit(form, id, body.answers, body.test, user)
    return Submitted(id=id, response_number=doc["response_number"])


@router.post("/forms/requisition/submissions/{id}/reverse")
def reverse(id: str, body: ReverseRequest, user: Annotated[str, needs("journal_entries:edit")]) -> Reversing:
    """A requisition's live entry undone: the correction workflow with no new lines posts its mirror, so the books
    balance, and replies in its thread. Asked here, so a page that's stale or a reason left blank start nothing"""
    return correction(id, body, user)


@router.post("/forms/requisition/submissions/{id}/correct")
def correct(id: str, body: CorrectRequest, user: Annotated[str, needs("journal_entries:edit")]) -> Reversing:
    """A requisition's live entry corrected: its mirror, then these lines, on its date and in its tenant. Each line's
    account must be one the entry's tenant can post to, and debits must equal credits"""
    debit, credit = (sum(x.amount for x in side) for side in (body.lines.debit, body.lines.credit))
    if abs(debit - credit) > 0.005:
        raise HTTPException(422, f"Debits ({debit:.2f}) and credits ({credit:.2f}) don't balance")
    entry = store.client().collection(JOURNAL).document(body.transaction_id).get().to_dict() or {}
    known = {a.glId: a for a in tenant_accounts(entry.get("tenant"))}
    if unknown := sorted({x.glId for x in body.lines.debit + body.lines.credit} - known.keys()):
        raise HTTPException(422, f"Not accounts this entry can post to: {', '.join(map(str, unknown))}")

    def lines(side):
        return [
            {"name": known[x.glId].name, "glCode": known[x.glId].glCode, "glId": x.glId, "amount": x.amount}
            for x in side
        ]

    return correction(id, body, user, {"debit": lines(body.lines.debit), "credit": lines(body.lines.credit)})


def correction(id: str, body: ReverseRequest, user: str, lines: dict | None = None) -> Reversing:
    """The correction workflow on the live entry, with lines or without: one run either way"""
    what = "corrected" if lines else "reversed"
    if not (reason := body.reason.strip()):
        raise HTTPException(422, f"Say why it's {what}")
    doc = store.submission("requisition", id).get()
    if doc.get("live_entry") != body.transaction_id:
        raise HTTPException(409, f"{body.transaction_id} isn't this requisition's live entry")
    argument = {"id": id, "reason": reason, "requested_by": user, "transaction_id": body.transaction_id}
    if lines:
        argument["lines"] = lines
    run = workflows.start("correction", argument)
    log(f"{'correction' if lines else 'reversal'} asked", id=id, transaction_id=body.transaction_id, run=run)
    return Reversing(run=run)


def tenant_accounts(tenant: str | None) -> list[Account]:
    # Without one, an entry from before entries kept their tenant: the services' own, where the workflow posts it too
    return [Account(**a) for a in services.get("/mifos/accounts", {"tenant": tenant} if tenant else {})]


@router.get("/accounts")
def accounts(_: Annotated[str, needs("journal_entries:edit")], tenant: str | None = None) -> list[Account]:
    """What a correction's lines can post to in an entry's tenant: expenser's accounts first, then by GL code"""
    return sorted(tenant_accounts(tenant), key=lambda a: (not a.expenser, a.glCode))


@router.get("/journal_entries")
def journal_entries(
    user: Annotated[str, needs("journal_entries:read")],
    cursor: str | None = None,
    limit: Limit = 25,
    tests: bool = False,
) -> JournalEntryPage:
    collection = store.client().collection(JOURNAL)
    # Entries are requisitions': whoever may make test requisitions may see their entries
    keep = None if shows_tests(user, "forms:requisition:test", tests) else no_test_entries
    docs, next = page(collection, "recorded_at", cursor, limit, keep)
    tests = test_entries(docs) if keep is None else set()
    return JournalEntryPage(
        items=[views.journal_entry(d.id, d.to_dict() | {"test": d.id in tests}) for d in docs], next=next
    )


@router.get("/journal_entries/{transaction_id}")
def journal_entry(transaction_id: str, _: Annotated[str, needs("journal_entries:read")]) -> JournalEntry:
    doc = store.client().collection(JOURNAL).document(transaction_id).get()
    if not doc.exists:
        raise HTTPException(404, f"No journal entry {transaction_id}")
    return views.journal_entry(doc.id, doc.to_dict())


FILES = {200: {"content": {"application/octet-stream": {}}}}
# A file's stored name, as our own form names it: what's safe in a path
NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def stream(name: str) -> StreamingResponse:
    """An object in our attachments bucket, streamed through, so it's behind IAP like the rest"""
    response = gcs.session().get(
        gcs.OBJECTS.format(bucket=gcs.bucket(), name=quote(name, safe="")),
        params={"alt": "media"},
        timeout=gcs.TIMEOUT,
        stream=True,
    )
    if not response.ok:
        raise HTTPException(404 if response.status_code == 404 else 502, gcs.reason(response))
    return StreamingResponse(
        response.iter_content(64 * 1024),
        media_type=response.headers.get("Content-Type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'inline; filename="{name.rsplit("/", 1)[-1]}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/files", response_class=StreamingResponse, responses=FILES)
def file(ref: str, _: Annotated[str, needs("files:read")]):
    """A file in our attachments bucket, by its gs:// ref. Drive's files open in Drive's own preview instead"""
    try:
        name_of_bucket, name = gcs.parse(ref)
    except gcs.GcsError as e:
        raise HTTPException(400, str(e)) from e
    if name_of_bucket != gcs.bucket():
        raise HTTPException(403, "Not our attachments bucket")
    return stream(name)


@router.get("/files/{form}/{id}/{name}", response_class=StreamingResponse, responses=FILES)
def submission_file(form: str, id: str, name: str, _: Annotated[str, needs("files:read")]):
    """A file added to a submission from our own form: a short link, for its emails"""
    known(form)
    if not (ID.match(id) and NAME.match(name)):
        raise HTTPException(400, "Not a file of ours")
    return stream(f"{form}/{id}/{name}")
