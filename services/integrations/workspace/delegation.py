"""Acting as lekkai@, through keyless domain-wide delegation (docs/phase6/adr.md 1 to 3).

The runtime account signs its own JWT through the IAM Credentials API, with sub set to the subject, and
trades it for a token that acts as the subject. No key exists. Blocking calls: run them in a thread.
"""

import functools
import os

import google.auth
import google.auth.exceptions
from google.auth import iam
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

TOKEN_URI = "https://oauth2.googleapis.com/token"
TIMEOUT = 30


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
