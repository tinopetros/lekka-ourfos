"""Who may do what. Every route names the permission it needs; this policy grants them, here in code, where a change is
a PR and its review.

A permission is `<what>:<action>`, a form's `forms:<form>:<action>`. A grant may use `*` for any part. Who is a
`user:` (an email), a `domain:` (everyone at it) or a `group:` (a Workspace group's members, nested groups' too).
An exclusion is the same, and wins over any grant: someone in a group that holds a permission can still be kept out of it.

An email is the one IAP says, the account's primary address, whichever alias was typed at sign-in.
"""

from fnmatch import fnmatchcase
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from forms import FORMS

from . import groups
from .auth import current_user

EVERYONE = "domain:lekkacredit.com"

POLICY: dict[str, list[str]] = {
    "forms:*:read": [EVERYONE],
    "forms:*:submit": [EVERYONE],
    "forms:*:test": ["group:tech@lekkacredit.com"],
    "journal_entries:read": ["group:directors@lekkacredit.com", "user:consultant-zsaruchera@lekkacredit.com"],
    "files:read": [EVERYONE],
}

EXCLUDE: dict[str, list[str]] = {
    "journal_entries:read": ["user:lekkai@lekkacredit.com"],
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
    if kind == "group":
        return name.lower() in groups.of(email)
    return False


def matches(policy: dict[str, list[str]], email: str, permission: str) -> bool:
    return any(
        fnmatchcase(permission, granted) and any(holds(email, who) for who in whom) for granted, whom in policy.items()
    )


def allowed(email: str, permission: str) -> bool:
    return matches(POLICY, email, permission) and not matches(EXCLUDE, email, permission)


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
