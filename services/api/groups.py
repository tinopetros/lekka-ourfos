"""Which Workspace groups someone is in, from Cloud Identity, as ourfos-api@: Groups Reader, an admin role assigned to
it in the Admin console. Nested groups count, walked up one level at a time: the transitive search is Enterprise
only. Kept 5 minutes a person, so a change in a group shows within 5 minutes."""

import functools
import os
import threading
import time

import google.auth
import google.auth.exceptions
import requests
from google.auth.transport.requests import AuthorizedSession

from common import log

DIRECT = "https://cloudidentity.googleapis.com/v1/groups/-/memberships:searchDirectGroups"
TTL = 300
# A lookup that failed is tried again sooner
RETRY = 30
TIMEOUT = 10

# Until when, and what
_cache: dict[str, tuple[float, frozenset[str]]] = {}
_lock = threading.Lock()


@functools.cache
def session() -> AuthorizedSession:
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-identity.groups.readonly"]
    )
    # Locally, your own account's: Cloud Identity bills a quota project, which user credentials don't have by default
    if not getattr(credentials, "quota_project_id", None) and hasattr(credentials, "with_quota_project"):
        credentials = credentials.with_quota_project(os.environ.get("GOOGLE_CLOUD_PROJECT", project))
    return AuthorizedSession(credentials)


def direct(member: str) -> set[str]:
    """The groups a person or group is directly in, by email."""
    groups, token = set(), None
    while True:
        # The member alone: the API refuses the label its docs ask for alongside
        params = {"query": f"member_key_id == '{member}'"} | ({"pageToken": token} if token else {})
        response = session().get(DIRECT, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
        groups |= {m["groupKey"]["id"].lower() for m in body.get("memberships", [])}
        if not (token := body.get("nextPageToken")):
            return groups


def lookup(email: str) -> frozenset[str]:
    found, todo = set(), [email]
    while todo:
        for group in direct(todo.pop()) - found:
            found.add(group)
            todo.append(group)
    return frozenset(found)


def of(email: str) -> frozenset[str]:
    """Every group someone is in, nested ones too. None, if Cloud Identity can't say: a group then grants nothing,
    and everything else still works."""
    with _lock:
        until, groups = _cache.get(email, (0.0, frozenset()))
        if time.monotonic() < until:
            return groups
    if "'" in email:
        return frozenset()
    try:
        groups, ttl = lookup(email), TTL
    except (requests.RequestException, google.auth.exceptions.GoogleAuthError, KeyError) as e:
        log("groups unknown", "WARNING", user=email, error=str(e))
        groups, ttl = frozenset(), RETRY
    with _lock:
        _cache[email] = (time.monotonic() + ttl, groups)
    return groups
