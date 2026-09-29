import json
import os

import functions_framework
from google.cloud.workflows import executions_v1

from auth import authorized
from form import Invalid, clean

client = executions_v1.ExecutionsClient()

# ?workflow= picks one: its cleaner, and the workflow Terraform named. One webhook URL per form
WORKFLOWS = {
    "requisition": (
        clean,
        client.workflow_path(os.environ["PROJECT_ID"], os.environ["REGION"], os.environ["WORKFLOW"]),
    ),
}


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
    name = request.args.get("workflow")
    if name not in WORKFLOWS:
        return {"error": f"?workflow= must be one of: {', '.join(WORKFLOWS)}"}, 400
    cleaner, workflow = WORKFLOWS[name]
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return {"error": "body must be a JSON object"}, 400

    # Beside the form's keys, from dev fixtures only. The prod workflow drops it
    simulate = raw.pop("simulate", None)
    try:
        requisition = cleaner(raw)
    except Invalid as e:
        # Still a run, which only hands over: with the form's add-on off, it's how anyone hears (phase 9 ADR 5)
        execution_id = start(workflow, {"invalid": "; ".join(e.errors), "raw": raw, "simulate": simulate})
        # The problems, never the values
        log(
            "rejected by cleaning",
            "WARNING",
            errors=[error.split(":")[0] for error in e.errors],
            execution_id=execution_id,
        )
        return {"errors": e.errors, "execution_id": execution_id}, 400

    execution_id = start(workflow, {"requisition": requisition.to_json(), "raw": raw, "simulate": simulate})
    log("started", workflow=name, execution_id=execution_id, response_number=requisition.response_number)
    return {"execution_id": execution_id}, 202


def start(workflow: str, argument: dict) -> str:
    execution = client.create_execution(parent=workflow, execution={"argument": json.dumps(argument)})
    return execution.name.rsplit("/", 1)[-1]
