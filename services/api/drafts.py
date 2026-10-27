"""Drafts: a submission of our own form before it's submitted, saved as it's filled in. A draft takes anything, as
typed: the form's model is the submit's. Only its author sees it, edits it, adds files to it or discards it.

A draft has no received_at, so lists, which order by it, leave it out on their own."""

import re
import uuid

from fastapi import HTTPException
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
from pydantic import BaseModel

import store
from forms import FORMS
from integrations import gcs
from submission import kinds

DRAFT = "draft"
# A file's name as stored: what's safe in a URL and a path, the rest made a dash
UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_FILE = 25 * 1024 * 1024


def ref(form: str, id: str):
    return store.client().collection(FORMS[form].collection).document(id)


def mine(form: str, id: str, user: str) -> dict | None:
    """The draft, if it's this person's; None, if there's nothing yet. Refused if it's submitted, or someone else's."""
    doc = ref(form, id).get().to_dict()
    if doc is None:
        return None
    if doc.get("submitted_by") != user:
        raise HTTPException(403, "Someone else's")
    if doc.get("status") != DRAFT:
        raise HTTPException(409, "Already submitted")
    return doc


def save(form: str, id: str, values: dict, test: bool, user: str):
    started = {} if mine(form, id, user) else {"created_at": SERVER_TIMESTAMP}
    ref(form, id).set(
        {
            "form": form,
            "source": "ourfos",
            "status": DRAFT,
            "submitted_by": user,
            "draft": values,
            "test": test,
            "updated_at": SERVER_TIMESTAMP,
        }
        | started,
        merge=True,
    )


def prefix(form: str, id: str) -> str:
    return f"{form}/{id}/"


def discard(form: str, id: str, user: str):
    if mine(form, id, user) is None:
        raise HTTPException(404, "No such draft")
    gcs.delete_prefix(prefix(form, id))
    ref(form, id).delete()


def upload(form: str, id: str, name: str, data: bytes, content_type: str, user: str) -> str:
    """A file for a draft, under the draft's own prefix, its name kept readable after a short tag that keeps two
    of the same name apart. The draft is made, if this is the first thing done on it."""
    if len(data) > MAX_FILE:
        raise HTTPException(413, "Files of up to 25 MB")
    if not data:
        raise HTTPException(400, "An empty file")
    if mine(form, id, user) is None:
        save(form, id, {}, False, user)
    safe = UNSAFE.sub("-", name).strip("-.")[:100] or "file"
    return gcs.upload(
        f"{prefix(form, id)}{uuid.uuid4().hex[:8]}-{safe}", data, content_type or "application/octet-stream"
    )


def file_questions(model: type[BaseModel]) -> list[tuple[str, ...]]:
    """Where a form asks for files: a question, or one in a group of them, like a requisition's."""
    paths = []
    for key, field in model.model_fields.items():
        if kinds(model)[key] == "files":
            paths.append((key,))
        elif isinstance(field.annotation, type) and issubclass(field.annotation, BaseModel):
            paths += [(key, *sub) for sub in file_questions(field.annotation)]
    return paths


def check_files(form: str, id: str, answers: dict):
    """Every file a submission names is one uploaded to it: never another's, nor Drive's."""
    for path in file_questions(FORMS[form].model):
        value = answers
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        for r in value if isinstance(value, list) else []:
            if not (isinstance(r, str) and r.startswith(f"gs://{gcs.bucket()}/{prefix(form, id)}")):
                raise HTTPException(422, [{"loc": list(path), "msg": "Not a file added to this submission"}])


def title(form: str, values: dict) -> str | None:
    named = " ".join(
        str(values[k]).strip() for k in FORMS[form].subject if isinstance(values.get(k), str) and values[k].strip()
    )
    return named or None


def list_mine(form: str, user: str) -> list[tuple[str, dict]]:
    """This person's drafts of a form, the latest first. Two equalities, so Firestore needs no index of ours"""
    query = (
        store.client()
        .collection(FORMS[form].collection)
        .where(filter=FieldFilter("submitted_by", "==", user))
        .where(filter=FieldFilter("status", "==", DRAFT))
    )
    docs = [(d.id, d.to_dict()) for d in query.stream()]
    return sorted(docs, key=lambda d: str(d[1].get("updated_at") or ""), reverse=True)
