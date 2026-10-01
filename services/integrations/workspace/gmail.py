"""Gmail as lekkai@: a submission's emails, in one thread we start (docs/phase9/tdd.md). Blocking: run in a thread."""

import base64
from email.headerregistry import Address
from email.message import EmailMessage

from integrations.workspace.delegation import call, subject

GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_USER = "https://gmail.googleapis.com/gmail/v1/users/me"


def message(
    to: list[str],
    sender_name: str,
    subject_line: str,
    html: str,
    text: str,
    in_reply_to: str | None = None,
    reply_to: list[str] | None = None,
) -> EmailMessage:
    """HTML with a plain-text alternative. A reply points at the first email, so any client threads it."""
    m = EmailMessage()
    m["From"] = Address(sender_name, addr_spec=subject())
    m["To"] = ", ".join(to)
    if reply_to:
        m["Reply-To"] = ", ".join(reply_to)
    m["Subject"] = " ".join(subject_line.split())
    if in_reply_to:
        m["In-Reply-To"] = m["References"] = in_reply_to
    m.set_content(text)
    m.add_alternative(html, subtype="html")
    return m


def send(
    to: list[str],
    sender_name: str,
    subject_line: str,
    html: str,
    text: str,
    thread: dict | None = None,
    reply_to: list[str] | None = None,
) -> dict:
    """A new thread, or a reply in one: {thread_id, in_reply_to} from the first email's send."""
    m = message(to, sender_name, subject_line, html, text, thread and thread["in_reply_to"], reply_to)
    body = {"raw": base64.urlsafe_b64encode(m.as_bytes()).decode()}
    if thread:
        body["threadId"] = thread["thread_id"]
    sent = call(GMAIL_SEND, "POST", f"{GMAIL_USER}/messages/send", json=body).json()
    return {"message_id": sent["id"], "thread_id": sent["threadId"]}


# RFC 822 is email's standard: its Message-ID header is what mail clients thread on, not Gmail's own API id
def rfc822_id(message_id: str) -> str:
    """The Message-ID Gmail gave an email we sent, for replies to point at."""
    got = call(
        GMAIL_READ,
        "GET",
        f"{GMAIL_USER}/messages/{message_id}",
        params={"format": "metadata", "metadataHeaders": ["Message-ID"]},
    ).json()
    headers = {h["name"].lower(): h["value"] for h in got.get("payload", {}).get("headers", [])}
    return headers["message-id"]
