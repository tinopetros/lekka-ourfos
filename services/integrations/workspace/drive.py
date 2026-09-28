"""Drive as lekkai@: a requisition's files, for the model."""

import base64

from integrations.workspace.delegation import call

DRIVE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"

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
