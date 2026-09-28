"""Drive and Gmail as lekkai@, through keyless domain-wide delegation (docs/phase6/adr.md 1 to 3).

The runtime account signs its own JWT through the IAM Credentials API, with sub set to the subject, and
trades it for a token that acts as the subject. No key exists. Blocking calls: run them in a thread.
"""

import base64
import functools
import os
from email.message import EmailMessage

import google.auth
import google.auth.exceptions
from google.auth import iam
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

DRIVE = "https://www.googleapis.com/auth/drive.readonly"
GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"

TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
GMAIL_USER = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT = 30

# What Gemini takes inline. Google Docs, Sheets and Slides are exported as PDF first
SHOWN = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}
EXPORTED = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}
# Across a requisition. Vertex took 105 MB inline on dev (2026-09-28): this is about our own memory, which holds
# every file and a base64 copy of it on the way to the model
MAX_BYTES = 40 * 1024 * 1024


def subject() -> str:
    # Set by Terraform, never from a request: Workspace doesn't limit who we act as, so this does
    return os.environ["WORKSPACE_SUBJECT"]


@functools.cache
def session(scope: str) -> AuthorizedSession:
    """One per scope, cached. google-auth refreshes the token, signing a fresh JWT each time."""
    source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    # Cloud Run's credentials only know their email once refreshed. It's the runtime account: it signs as itself
    source.refresh(Request())
    signer_email = source.service_account_email
    credentials = service_account.Credentials(
        iam.Signer(Request(), source, signer_email),
        signer_email,
        TOKEN_URI,
        scopes=[scope],
        subject=subject(),
    )
    return AuthorizedSession(credentials)


class WorkspaceError(Exception):
    """A call Google answered with an error. status is Google's, so the caller can map it."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def call(scope: str, method: str, url: str, **kwargs):
    try:
        response = session(scope).request(method, url, timeout=TIMEOUT, **kwargs)
    except google.auth.exceptions.RefreshError as e:
        # Usually the Admin console: the client id isn't granted this scope yet
        raise WorkspaceError(401, f"cannot act as {subject()}: {e}") from e
    if not response.ok:
        raise WorkspaceError(response.status_code, f"{response.status_code} {reason(response)}")
    return response


def reason(response) -> str:
    """Google's own message, e.g. "File not found: <id>.", rather than its whole error document."""
    try:
        return str(response.json()["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return response.text[:200]


# Drive


def fetch(file_id: str) -> dict:
    """A file's type and bytes, as the subject sees it. Google-native files come back as PDF."""
    meta = call(DRIVE, "GET", f"{DRIVE_FILES}/{file_id}", params={"fields": "mimeType"}).json()
    if meta["mimeType"] in EXPORTED:
        data = call(DRIVE, "GET", f"{DRIVE_FILES}/{file_id}/export", params={"mimeType": "application/pdf"}).content
        mime_type = "application/pdf"
    else:
        data = call(DRIVE, "GET", f"{DRIVE_FILES}/{file_id}", params={"alt": "media"}).content
        mime_type = meta["mimeType"]
    return {"id": file_id, "mimeType": mime_type, "size": len(data), "data": data}


def to_base64(data: bytes) -> str:
    """For looking at a part by hand. The SDK base64s bytes itself on the wire."""
    return base64.b64encode(data).decode()


# Gmail


def headers(message: dict, *names: str) -> dict:
    found = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
    return {name.lower(): found.get(name.lower()) for name in names}


def messages(subject_contains: str, limit: int = 10) -> list[dict]:
    listed = call(
        GMAIL_READ, "GET", f"{GMAIL_USER}/messages", params={"q": f'subject:"{subject_contains}"', "maxResults": limit}
    ).json()
    found = []
    for m in listed.get("messages", []):
        message = call(
            GMAIL_READ,
            "GET",
            f"{GMAIL_USER}/messages/{m['id']}",
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
        ).json()
        found.append(
            {"id": message["id"], "threadId": message["threadId"]} | headers(message, "Subject", "From", "Date")
        )
    return found


def thread(thread_id: str) -> list[dict]:
    got = call(
        GMAIL_READ,
        "GET",
        f"{GMAIL_USER}/threads/{thread_id}",
        params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
    ).json()
    return [
        {"id": m["id"], "snippet": m.get("snippet", "")} | headers(m, "Subject", "From", "To", "Date")
        for m in got.get("messages", [])
    ]


def send_to_self(subject_line: str, body: str) -> dict:
    """Only ever to the subject itself: proves gmail.send without mailing anyone (docs/phase6/adr.md 5)."""
    message = EmailMessage()
    message["To"] = message["From"] = subject()
    message["Subject"] = subject_line
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = call(GMAIL_SEND, "POST", f"{GMAIL_USER}/messages/send", json={"raw": raw}).json()
    return {"id": sent["id"], "threadId": sent["threadId"]}
