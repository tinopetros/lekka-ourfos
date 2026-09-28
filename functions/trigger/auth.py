import hmac


def authorized(header: str | None, token: str | None) -> bool:
    """Bearer <token>, compared in constant time (docs/phase6/adr.md 6)."""
    scheme, _, given = (header or "").partition(" ")
    return bool(token) and scheme.lower() == "bearer" and hmac.compare_digest(given.encode(), token.encode())
