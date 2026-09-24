import json
import time

from fastapi import HTTPException, Request


def log(request: Request, message: str, severity: str = "INFO", **fields):
    # One JSON line per event, so Cloud Logging can filter on jsonPayload.execution_id
    print(json.dumps({
        "severity": severity,
        "message": message,
        "execution_id": request.headers.get("x-execution-id"),
        **fields,
    }), flush=True)


def simulate(request: Request, step: str, code):
    """Force a failure from the fixture: an HTTP status, or "timeout" to hang past the workflow's timeout."""
    if not code:
        return
    log(request, f"simulating {code}", "WARNING", step=step)
    if code == "timeout":
        time.sleep(40)
    elif isinstance(code, int) or str(code).isdigit():
        raise HTTPException(int(code), f"simulated {code} at {step}")
