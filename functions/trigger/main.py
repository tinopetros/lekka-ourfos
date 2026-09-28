import json
import os

import functions_framework
from google.cloud.workflows import executions_v1

from auth import authorized
from form import Invalid, clean

client = executions_v1.ExecutionsClient()
workflow = client.workflow_path(os.environ["PROJECT_ID"], os.environ["REGION"], os.environ["WORKFLOW"])


def log(message: str, severity: str = "INFO", **fields):
    print(json.dumps({"severity": severity, "message": message} | fields), flush=True)


@functions_framework.http
def trigger(request):
    token = os.environ.get("TRIGGER_TOKEN")
    if not token:
        # Never fails open
        log("no token configured", "ERROR")
        return {"error": "not configured"}, 500
    if not authorized(request.headers.get("Authorization"), token):
        # Before the body is read, so nothing of it is logged or cleaned
        log("unauthorized", "WARNING")
        return {"error": "unauthorized"}, 401, {"WWW-Authenticate": "Bearer"}
    if request.method != "POST":
        return {"error": "POST a requisition"}, 405
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return {"error": "body must be a JSON object"}, 400

    # Beside the form's keys, from dev fixtures only. The prod workflow drops it
    simulate = raw.pop("simulate", None)
    try:
        requisition = clean(raw)
    except Invalid as e:
        # The problems, never the values
        log("rejected by cleaning", "WARNING", errors=[error.split(":")[0] for error in e.errors])
        return {"errors": e.errors}, 400

    argument = {"requisition": requisition.to_json(), "raw": raw, "simulate": simulate}
    execution = client.create_execution(parent=workflow, execution={"argument": json.dumps(argument)})
    execution_id = execution.name.rsplit("/", 1)[-1]
    log("started", execution_id=execution_id, response_number=requisition.response_number)
    return {"execution_id": execution_id}, 202
