"""Who's signed in

On Cloud Run, IAP has already signed them in, and says who in a JWT it signs: we check its signature, audience and
issuer, and nothing else gets through. Locally, there's no IAP: who you are is your ADC account, or ACT_AS. Refused on
Cloud Run, so a deployed service can never be told who's asking.
"""

import os
import threading
import time

import google.auth
import requests
from fastapi import HTTPException, Request
from google.api_core import exceptions
from google.auth import jwt
from google.auth.transport.requests import Request as AuthRequest

import store
from common import log

HEADER = "x-goog-iap-jwt-assertion"
ISSUER = "https://cloud.google.com/iap"
CERTS = "https://www.gstatic.com/iap/verify/public_key"
# IAP rotates its keys: kept an hour, and fetched again when a token names a key we don't have
CERTS_TTL = 3600
# A user's last_seen, at most this often per instance
SEEN_EVERY = 300

_certs: dict = {"keys": {}, "at": 0.0}
_seen: dict[str, float] = {}
_lock = threading.Lock()


def local() -> bool:
    if os.environ.get("AUTH") != "local":
        return False
    if os.environ.get("K_SERVICE"):
        raise RuntimeError("AUTH=local is refused on Cloud Run")
    return True


def certs(refresh: bool = False) -> dict:
    with _lock:
        if refresh or time.monotonic() - _certs["at"] > CERTS_TTL:
            response = requests.get(CERTS, timeout=10)
            response.raise_for_status()
            _certs.update(keys=response.json(), at=time.monotonic())
        return _certs["keys"]


def verify(token: str, audience: str) -> str:
    """The email in IAP's JWT, once its signature, audience and issuer check out."""
    try:
        claims = jwt.decode(token, certs=certs(), audience=audience, clock_skew_in_seconds=30)
    except ValueError as e:
        # An unknown key: IAP rotated since we fetched them
        if "Certificate for key id" not in str(e):
            raise
        claims = jwt.decode(token, certs=certs(refresh=True), audience=audience, clock_skew_in_seconds=30)
    if claims.get("iss") != ISSUER or not claims.get("email"):
        raise ValueError("not IAP's")
    return claims["email"].lower()


_adc_email: dict = {}


def adc_email() -> str:
    """Who your application default credentials are: a person's account, or a service account's."""
    if "email" not in _adc_email:
        credentials, _ = google.auth.default(scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"])
        if email := getattr(credentials, "service_account_email", None):
            _adc_email["email"] = email
        else:
            credentials.refresh(AuthRequest())
            info = requests.get(
                "https://oauth2.googleapis.com/tokeninfo", params={"access_token": credentials.token}, timeout=10
            ).json()
            _adc_email["email"] = info["email"]
    return _adc_email["email"].lower()


def current_user(request: Request) -> str:
    """The signed-in user's email. Every route takes it."""
    if local():
        email = (os.environ.get("ACT_AS") or adc_email()).lower()
    else:
        token = request.headers.get(HEADER)
        if not token:
            raise HTTPException(401, "Not signed in")
        try:
            email = verify(token, os.environ["IAP_AUDIENCE"])
        except (ValueError, requests.RequestException) as e:
            log(f"refused: {e}", "WARNING")
            raise HTTPException(401, "Not signed in") from e
    # For the request log, which runs outside the thread a sync route's dependencies run in
    request.state.user = email
    seen(email)
    return email


def seen(email: str):
    """users/{email}: first_seen once, then last_seen. In the background, never in the way of a read."""
    now = time.monotonic()
    if now - _seen.get(email, -SEEN_EVERY) < SEEN_EVERY:
        return
    _seen[email] = now
    threading.Thread(target=record, args=(email,), daemon=True).start()


def record(email: str):
    """A failure is logged: a sign-in is still a sign-in."""
    try:
        ref = store.client().collection("users").document(email)
        try:
            ref.create({"email": email, "first_seen": store.NOW, "last_seen": store.NOW})
        except exceptions.AlreadyExists:
            ref.update({"last_seen": store.NOW})
    except Exception as e:  # noqa: BLE001  a sign-in is still a sign-in
        log(f"user not recorded: {e}", "ERROR", user=email)
