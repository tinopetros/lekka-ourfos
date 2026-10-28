"""No test reaches a real database, nor Workspace's groups: anything a test doesn't fake fails loudly, rather than writing through whatever
credentials the laptop has."""

import pytest

import store
from api import groups


@pytest.fixture(autouse=True)
def no_firestore(monkeypatch):
    def refuse():
        raise RuntimeError("a test reached Firestore: fake what it writes")

    monkeypatch.setattr(store, "client", refuse)


@pytest.fixture(autouse=True)
def groups_of(monkeypatch):
    """Who's in which group, by email, for a test to fill in: in none, unless it does."""
    members: dict[str, set[str]] = {}
    monkeypatch.setattr(groups, "of", lambda email: frozenset(members.get(email, set())))
    return members
