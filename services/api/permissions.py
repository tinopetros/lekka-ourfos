"""Who may do what. Every route names the permission it needs; this policy grants them, here in code, where a change is
a PR and its review.

A permission is `<what>:<action>`, a form's `forms:<form>:<action>`. A grant may use `*` for any part. Who is a
`user:` (an email), a `domain:` (everyone at it) or a `group:` (a Workspace group's members). Groups count once
their members are synced from Workspace's directory: until then a group grants no one.
"""

from fnmatch import fnmatchcase
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from forms import FORMS

from .auth import current_user

EVERYONE = "domain:lekkacredit.com"

POLICY: dict[str, list[str]] = {
    "forms:*:read": [EVERYONE],
    "forms:*:submit": [EVERYONE],
    # A test submission never posts, but it emails and numbers like any other: only for whoever is testing ourfos
    "forms:*:test": ["user:tpetros@lekkacredit.com"],
    "journal_entries:read": [EVERYONE],
    "files:read": [EVERYONE],
}

# Every permission there is, for /me to list
PERMISSIONS = [
    *(f"forms:{form}:{action}" for form in FORMS for action in ("read", "submit", "test")),
    "journal_entries:read",
    "files:read",
]


def holds(email: str, who: str) -> bool:
    kind, _, name = who.partition(":")
    if kind == "user":
        return email == name.lower()
    if kind == "domain":
        return email.endswith(f"@{name.lower()}")
    # group: once memberships are synced
    return False


def allowed(email: str, permission: str) -> bool:
    return any(
        fnmatchcase(permission, granted) and any(holds(email, who) for who in whom) for granted, whom in POLICY.items()
    )


def granted(email: str) -> list[str]:
    return [p for p in PERMISSIONS if allowed(email, p)]


def needs(permission: str):
    """A route's permission, its path's parameters filled in, e.g. `forms:{form}:read`. Who's signed in, if they hold
    it; a 403 otherwise."""

    def check(request: Request, email: Annotated[str, Depends(current_user)]) -> str:
        wanted = permission.format(**request.path_params)
        if not allowed(email, wanted):
            raise HTTPException(403, f"You don't have {wanted}")
        return email

    return Depends(check)
