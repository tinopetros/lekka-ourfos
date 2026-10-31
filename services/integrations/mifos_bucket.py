"""The mifos bucket, where the mifos sync keeps what it reads from Mifos. Prod only: MIFOS_BUCKET is set where the sync
is scheduled, and nowhere else. Blocking calls."""

import functools
import os
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

OBJECTS = "https://storage.googleapis.com/storage/v1/b/{bucket}/o"
UPLOAD = "https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
TIMEOUT = 60


def bucket() -> str | None:
    return os.environ.get("MIFOS_BUCKET") or None


@functools.cache
def session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
    return AuthorizedSession(credentials)


def read(name: str) -> str | None:
    """An object's text, or None if there's no such object."""
    response = session().get(
        f"{OBJECTS.format(bucket=bucket())}/{quote(name, safe='')}", params={"alt": "media"}, timeout=TIMEOUT
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.content.decode()


def write(name: str, text: str):
    response = session().post(
        UPLOAD.format(bucket=bucket()),
        params={"uploadType": "media", "name": name},
        data=text.encode(),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()


def append(name: str, text: str):
    """GCS can't append: read, add, write back. Only for the small logs, and only one sync of a kind at a time."""
    write(name, (read(name) or "") + text)


def names(prefix: str) -> list[str]:
    """The objects under prefix, sorted."""
    found, token = [], None
    while True:
        params = {"prefix": prefix, "fields": "items(name),nextPageToken"} | ({"pageToken": token} if token else {})
        response = session().get(OBJECTS.format(bucket=bucket()), params=params, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
        found += [item["name"] for item in body.get("items", [])]
        token = body.get("nextPageToken")
        if not token:
            return sorted(found)
