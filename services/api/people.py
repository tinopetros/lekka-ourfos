"""Someone's full name, from Workspace's directory, as ourfos-api@: ourfos user reader, a custom admin role assigned to
it in the Admin console, Users → Read only. Kept on users/{email} and checked again after a week, never deleted: when
the directory can't say, the name last seen stands, and without one, the email."""

import functools
import threading
import time
from datetime import UTC, datetime, timedelta

import google.auth
import google.auth.exceptions
import requests
from google.auth.transport.requests import AuthorizedSession

import store
from common import log

USERS = "https://admin.googleapis.com/admin/directory/v1/users/"
DOMAIN = "@lekkacredit.com"
# How old a saved name may be before the directory is asked again: names rarely change
FRESH = timedelta(days=7)
# On an instance, so a page of submissions isn't a read a row
TTL = 300
TIMEOUT = 10

_cache: dict[str, tuple[float, str | None]] = {}
_lock = threading.Lock()


@functools.cache
def session() -> AuthorizedSession:
    # Billed to the account's own project: naming one takes serviceusage.services.use, which ourfos-api@ hasn't. Locally,
    # your ADC names its own, as for groups
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"])
    return AuthorizedSession(credentials)


def directory(email: str) -> str | None:
    """Their full name, or None if they have none. Raises if the directory can't be asked."""
    response = session().get(f"{USERS}{email}", params={"fields": "name/fullName"}, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    if not response.ok:
        # The directory's own reason, e.g. which privilege is missing: a status alone says little
        raise requests.HTTPError(f"{response.status_code}: {response.text[:300]}", response=response)
    return response.json().get("name", {}).get("fullName") or None


def lookup(email: str) -> str | None:
    ref = store.client().collection("users").document(email)
    saved = ref.get()
    saved = saved.to_dict() if saved.exists else {}
    checked = saved.get("name_checked_at")
    if checked and datetime.now(UTC) - checked < FRESH:
        return saved.get("name")
    try:
        name = directory(email)
    except (requests.RequestException, google.auth.exceptions.GoogleAuthError, ValueError) as e:
        log("name unknown", "WARNING", user=email, error=str(e))
        return saved.get("name")
    ref.set({"email": email, "name": name, "name_checked_at": datetime.now(UTC)}, merge=True)
    return name


def name(email: str) -> str | None:
    """Their full name, if anyone has ever told us. Only ours: the directory knows nobody else."""
    email = email.lower()
    if not email.endswith(DOMAIN) or "/" in email:
        return None
    with _lock:
        until, known = _cache.get(email, (0.0, None))
        if time.monotonic() < until:
            return known
    try:
        known = lookup(email)
    except Exception as e:  # noqa: BLE001  a name is a nicety: the email still shows
        log(f"name not read: {e}", "ERROR", user=email)
        return None
    with _lock:
        _cache[email] = (time.monotonic() + TTL, known)
    return known
