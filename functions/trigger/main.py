import json
import os

import functions_framework
from google.cloud.workflows import executions_v1

from auth import authorized
from form import Invalid, clean, flag
from forms import FORMS
from submission import ID

client = executions_v1.ExecutionsClient()

# ?workflow= names the form, as its webhook always has, and the form names its workflow (docs/phase10/tdd.md)
WORKFLOWS = {
    name: client.workflow_path(os.environ["PROJECT_ID"], os.environ["REGION"], form.workflow)
    for name, form in FORMS.items()
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
        return {"error": "POST a form"}, 405
    name = request.args.get("workflow")
    if name not in WORKFLOWS:
        return {"error": f"?workflow= must be one of: {', '.join(WORKFLOWS)}"}, 400
    workflow = WORKFLOWS[name]
    # A real run that tells only lekkai@ and its submitter (docs/release1/adr.md 3)
    try:
        test = flag(request.args.get("test"))
    except ValueError:
        return {"error": "?test= must be true or false"}, 400
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return {"error": "body must be a JSON object"}, 400

    # Beside the form's keys, from dev fixtures only. The prod workflow drops it
    simulate = raw.pop("simulate", None)
    try:
        submission = clean(raw, name)
    except Invalid as e:
        # Still a run, which only hands over: with the form's add-on off, it's how anyone hears (phase 9 ADR 5).
        # Stored under its response_id when that's usable, otherwise under the run's own id
        response_id = raw.get("response_id")
        id = {"id": response_id} if isinstance(response_id, str) and ID.match(response_id) else {}
        execution_id = start(
            workflow,
            {"form": name, **id, "invalid": "; ".join(e.errors), "raw": raw, "simulate": simulate, "test": test},
        )
        # The problems, never the values
        log(
            "rejected by cleaning",
            "WARNING",
            form=name,
            errors=[error.split(":")[0] for error in e.errors],
            execution_id=execution_id,
            test=test,
        )
        return {"errors": e.errors, "execution_id": execution_id}, 400

    id = submission.response_id
    execution_id = start(
        workflow,
        {"form": name, "id": id, "submission": submission.to_json(), "raw": raw, "simulate": simulate, "test": test},
    )
    log("started", form=name, execution_id=execution_id, response_number=submission.response_number, test=test)
    return {"execution_id": execution_id, "id": id}, 202


def start(workflow: str, argument: dict) -> str:
    execution = client.create_execution(parent=workflow, execution={"argument": json.dumps(argument)})
    return execution.name.rsplit("/", 1)[-1]
