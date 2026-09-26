import json
import time
from contextvars import ContextVar

from fastapi import HTTPException

# The workflow's is_transient: these pass through so it retries them
RETRIED = (429, 502, 503, 504)

# Set per request from X-Execution-Id, so modules log without being handed the request
execution_id: ContextVar[str | None] = ContextVar("execution_id", default=None)


def log(message: str, severity: str = "INFO", **fields):
    # One JSON line per event, so Cloud Logging can filter on jsonPayload.execution_id
    entry = {"severity": severity, "message": message, "execution_id": execution_id.get()}
    print(json.dumps(entry | fields, default=str), flush=True)


def simulate(step: str, code):
    """Force a failure from the fixture: an HTTP status, or "timeout" to hang past the workflow's timeout."""
    if not code:
        return
    log(f"simulating {code}", "WARNING", step=step)
    if code == "timeout":
        time.sleep(70)  # past every step timeout, including classify's 60s
    elif isinstance(code, int) or str(code).isdigit():
        raise HTTPException(int(code), f"simulated {code} at {step}")
