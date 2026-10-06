"""No test reaches a real database: anything a test doesn't fake fails loudly, rather than writing through whatever
credentials the laptop has."""

import pytest

import store


@pytest.fixture(autouse=True)
def no_firestore(monkeypatch):
    def refuse():
        raise RuntimeError("a test reached Firestore: fake what it writes")

    monkeypatch.setattr(store, "client", refuse)
