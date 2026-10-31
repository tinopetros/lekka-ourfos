"""Starting a workflow's run, as the runtime account."""

import functools
import json
import os

import google.auth
from google.auth.transport.requests import AuthorizedSession

EXECUTIONS = (
    "https://workflowexecutions.googleapis.com/v1/projects/{project}/locations/{region}/workflows/{workflow}/executions"
)
TIMEOUT = 30


@functools.cache
def session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def state(workflow: str, execution_id: str) -> tuple[str, str | None]:
    """A run's state, ACTIVE, SUCCEEDED, FAILED or CANCELLED, and its error's message when it failed"""
    url = EXECUTIONS.format(project=os.environ["GOOGLE_CLOUD_PROJECT"], region=os.environ["REGION"], workflow=workflow)
    response = session().get(f"{url}/{execution_id}", timeout=TIMEOUT)
    response.raise_for_status()
    execution = response.json()
    error = (execution.get("error") or {}).get("payload")
    try:
        error = json.loads(error).get("message", error) if error else None
    except (ValueError, AttributeError):
        pass
    return execution["state"], error


def start(workflow: str, argument: dict) -> str:
    """A run of the workflow, with its argument. Its execution id."""
    url = EXECUTIONS.format(project=os.environ["GOOGLE_CLOUD_PROJECT"], region=os.environ["REGION"], workflow=workflow)
    response = session().post(url, json={"argument": json.dumps(argument)}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["name"].rsplit("/", 1)[-1]
