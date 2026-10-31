"""What the API starts the correction workflow with reaches the services: a key the workflow doesn't forward is a run
refused for want of it."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[2] / "workflows" / "correction.workflows.yaml"


def steps(node):
    """Every step in the workflow, however deep in try, except and nested steps it sits"""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict) and "call" in v:
                yield k, v
            yield from steps(v)
    elif isinstance(node, list):
        for x in node:
            yield from steps(x)


def test_every_argument_a_correction_reversal_or_post_is_started_with_reaches_the_services():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    [body] = [s["args"]["body"] for _, s in steps(workflow) if s.get("args", {}).get("path") == "/correction"]
    # The API's: a reversal, a correction's lines, a post's filing. The id is the path's
    assert {"reason", "requested_by", "transaction_id", "lines", "post"} <= body.keys()
