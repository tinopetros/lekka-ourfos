import pytest

from auth import authorized

TOKEN = "s3cret-token"


@pytest.mark.parametrize("header", ["Bearer s3cret-token", "bearer s3cret-token"])
def test_authorized(header):
    assert authorized(header, TOKEN)


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer ", "Bearer wrong", "Basic s3cret-token", "s3cret-token", "Bearer s3cret-token "],
)
def test_unauthorized(header):
    assert not authorized(header, TOKEN)


@pytest.mark.parametrize("token", [None, ""])
def test_no_token_configured_never_authorizes(token):
    assert not authorized("Bearer ", token)
    assert not authorized("Bearer x", token)
