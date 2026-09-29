"""Our attachments bucket, as the runtime account (docs/phase7/adr.md 1 and 2). Blocking calls: run them in a thread."""

import functools
import os
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

OBJECTS = "https://storage.googleapis.com/storage/v1/b/{bucket}/o/{name}"
TIMEOUT = 30


class GcsError(Exception):
    """A ref we won't read, or one GCS answered with an error. status is GCS's, so the caller can map it."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def bucket() -> str:
    # Set by Terraform, never from a request: a ref names its bucket, and only this one is ours to read
    return os.environ["ATTACHMENTS_BUCKET"]


@functools.cache
def session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_only"])
    return AuthorizedSession(credentials)


def parse(ref: str) -> tuple[str, str]:
    """gs://<bucket>/<name> into its bucket and name."""
    name_of_bucket, _, name = ref.removeprefix("gs://").partition("/")
    if not ref.startswith("gs://") or not name_of_bucket or not name:
        raise GcsError(400, f"not a gs:// ref: {ref}")
    return name_of_bucket, name


def fetch(ref: str) -> dict:
    """An object's type and bytes, in one call: GCS answers alt=media with the content type it was stored with."""
    name_of_bucket, name = parse(ref)
    if name_of_bucket != bucket():
        raise GcsError(403, f"not our attachments bucket: {name_of_bucket}")
    response = session().get(
        OBJECTS.format(bucket=name_of_bucket, name=quote(name, safe="")), params={"alt": "media"}, timeout=TIMEOUT
    )
    if not response.ok:
        raise GcsError(response.status_code, f"{response.status_code} {reason(response)}")
    data = response.content
    mime_type = response.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
    return {"id": ref, "mimeType": mime_type, "size": len(data), "data": data}


def reason(response) -> str:
    """GCS's own message, e.g. "No such object: …", rather than its whole error document."""
    try:
        return str(response.json()["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return response.text[:200]
