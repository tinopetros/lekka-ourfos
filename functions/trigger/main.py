import json
import os

import functions_framework
from google.cloud.workflows import executions_v1

client = executions_v1.ExecutionsClient()
workflow = client.workflow_path(os.environ["PROJECT_ID"], os.environ["REGION"], os.environ["WORKFLOW"])


@functions_framework.http
def trigger(request):
    if request.method != "POST":
        return {"error": "POST a requisition"}, 405
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return {"error": "body must be a JSON object"}, 400

    execution = client.create_execution(parent=workflow, execution={"argument": json.dumps(body)})
    execution_id = execution.name.rsplit("/", 1)[-1]
    print(json.dumps({"severity": "INFO", "message": "started", "execution_id": execution_id}), flush=True)
    return {"execution_id": execution_id}, 202
