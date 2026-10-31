"""ourfos-services, called by ourfos-api as itself: what the API reads but keeps no credentials for, Mifos's accounts."""

import os

import google.auth.transport.requests
import google.oauth2.id_token
from fastapi import HTTPException

from common import log

# Under the UI's patience: the services read Mifos in about a second, or answer from what they last read
TIMEOUT = 20


def get(path: str, params: dict) -> list | dict:
    url = os.environ["SERVICES_URL"]
    request = google.auth.transport.requests.Request()
    # Locally, the services run beside the API with no Cloud Run in front. There, Cloud Run checks the token is for
    # it: its own URL is the audience
    local = os.environ.get("ENVIRONMENT") == "local"
    headers = {} if local else {"Authorization": f"Bearer {google.oauth2.id_token.fetch_id_token(request, url)}"}
    response = request.session.get(f"{url}{path}", params=params, headers=headers, timeout=TIMEOUT)
    if not response.ok:
        log(f"services {path}: {response.status_code} {response.text[:200]}", "ERROR")
        raise HTTPException(502, f"Couldn't read {path} from ourfos-services")
    return response.json()
