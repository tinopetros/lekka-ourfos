"""Gmail as lekkai@, a setup check (docs/phase6/adr.md 5)."""

import base64
from email.message import EmailMessage

from integrations.workspace.delegation import call, subject

GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_USER = "https://gmail.googleapis.com/gmail/v1/users/me"


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
