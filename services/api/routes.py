import os
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from google.cloud import firestore

import store
from forms import FORMS
from integrations import gcs

from . import views
from .auth import current_user
from .models import FormInfo, JournalEntry, JournalEntryPage, Me, Submission, SubmissionPage

# Each route's operation named by its function: the generated TypeScript's names
router = APIRouter(prefix="/api", generate_unique_id_function=lambda route: route.name)
# journal.py's, not imported: it brings the Mifos connector, and nothing here reaches Mifos
JOURNAL = "journal_entries"
User = Annotated[str, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=100)]


def known(form: str):
    if form not in FORMS:
        raise HTTPException(404, f"No form {form}")


def page(collection, field: str, cursor: str | None, limit: int):
    """Newest first, cursor paginated. The cursor is the last document's id: the next page starts after it. One more
    than asked for says whether there's a next page."""
    query = collection.order_by(field, direction=firestore.Query.DESCENDING)
    if cursor:
        after = collection.document(cursor).get()
        if not after.exists:
            raise HTTPException(400, "That page is gone: start again")
        query = query.start_after(after)
    docs = list(query.limit(limit + 1).stream())
    return docs[:limit], docs[limit - 1].id if len(docs) > limit else None


@router.get("/me")
def me(email: User) -> Me:
    return Me(
        email=email,
        environment=os.environ.get("ENVIRONMENT", "local"),
        version=os.environ.get("VERSION", "local"),
    )


@router.get("/forms")
def forms(_: User) -> list[FormInfo]:
    return [FormInfo(key=form, title=spec.title) for form, spec in FORMS.items()]


@router.get("/forms/{form}/submissions")
def submissions(form: str, _: User, cursor: str | None = None, limit: Limit = 25) -> SubmissionPage:
    known(form)
    collection = store.client().collection(FORMS[form].collection)
    docs, next = page(collection, "received_at", cursor, limit)
    return SubmissionPage(items=[views.summary(form, d.id, d.to_dict()) for d in docs], next=next)


@router.get("/forms/{form}/submissions/{id}")
def submission(form: str, id: str, _: User) -> Submission:
    known(form)
    ref = store.client().collection(FORMS[form].collection).document(id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(404, f"No {FORMS[form].noun} {id}")
    data = doc.to_dict()
    runs = [views.run(r.id, r.to_dict()) for r in ref.collection("runs").stream()]
    ids = data.get("journal_entries") or []
    refs = [store.client().collection(JOURNAL).document(i) for i in ids]
    entries = {e.id: e for e in store.client().get_all(refs) if e.exists}
    return views.submission(
        form, id, data, runs, [views.journal_entry(i, entries[i].to_dict()) for i in ids if i in entries]
    )


@router.get("/journal_entries")
def journal_entries(_: User, cursor: str | None = None, limit: Limit = 25) -> JournalEntryPage:
    collection = store.client().collection(JOURNAL)
    docs, next = page(collection, "recorded_at", cursor, limit)
    return JournalEntryPage(items=[views.journal_entry(d.id, d.to_dict()) for d in docs], next=next)


@router.get("/journal_entries/{transaction_id}")
def journal_entry(transaction_id: str, _: User) -> JournalEntry:
    doc = store.client().collection(JOURNAL).document(transaction_id).get()
    if not doc.exists:
        raise HTTPException(404, f"No journal entry {transaction_id}")
    return views.journal_entry(doc.id, doc.to_dict())


@router.get("/files", response_class=StreamingResponse, responses={200: {"content": {"application/octet-stream": {}}}})
def file(ref: str, _: User):
    """A file in our attachments bucket, streamed through, so it's behind IAP like the rest. Drive's files open in
    Drive's own preview instead"""
    try:
        name_of_bucket, name = gcs.parse(ref)
    except gcs.GcsError as e:
        raise HTTPException(400, str(e)) from e
    if name_of_bucket != gcs.bucket():
        raise HTTPException(403, "Not our attachments bucket")
    response = gcs.session().get(
        gcs.OBJECTS.format(bucket=name_of_bucket, name=quote(name, safe="")),
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
