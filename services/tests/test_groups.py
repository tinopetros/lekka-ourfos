"""Which groups someone is in, nested ones too, from Cloud Identity's direct groups one level at a time."""

import pytest
import requests

from api import groups

# Taken before conftest fakes it for every test
REAL = groups.of

# Who's directly in which groups
DIRECT = {
    "ada@lekkacredit.com": {"tech@lekkacredit.com"},
    "tech@lekkacredit.com": {"staff@lekkacredit.com"},
    "staff@lekkacredit.com": set(),
}


@pytest.fixture
def real(monkeypatch):
    """The real of(), over a fake Cloud Identity."""
    asked = []
    monkeypatch.setattr(groups, "of", REAL)
    monkeypatch.setattr(groups, "direct", lambda member: asked.append(member) or set(DIRECT.get(member, set())))
    monkeypatch.setattr(groups, "_cache", {})
    return asked


def test_a_persons_groups_include_their_groups_groups(real):
    assert groups.of("ada@lekkacredit.com") == {"tech@lekkacredit.com", "staff@lekkacredit.com"}


def test_a_persons_groups_are_kept_a_while(real):
    groups.of("ada@lekkacredit.com")
    groups.of("ada@lekkacredit.com")
    assert real.count("ada@lekkacredit.com") == 1


def test_groups_that_cant_be_read_grant_nothing(real, monkeypatch):
    def refused(member):
        raise requests.HTTPError("403: not Groups Reader")

    monkeypatch.setattr(groups, "direct", refused)
    assert groups.of("ada@lekkacredit.com") == frozenset()
