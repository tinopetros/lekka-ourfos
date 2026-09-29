"""Expenser against real requisitions (docs/phase7/tdd.md). Paid and slow: `make evals`, never `make test`.

RUNS (default 3) runs of every case, or of CASE alone. Passes when each metric's pass rate is at least BAR.
Configured as PROJECT's deployed ourfos-services is, so it scores the model and prompt that are live there.
"""

import asyncio
import csv
import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import google.auth
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet
from google.auth.transport.requests import AuthorizedSession

from evals.metrics import amounts_kind, parse

HERE = Path(__file__).parent
BAR = 0.70


def deployed_env(project: str, region: str) -> dict[str, str]:
    """ourfos-services' plain env vars, from Cloud Run: its model, Model Armor template and bucket."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    response = AuthorizedSession(credentials).get(
        f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/services/ourfos-services", timeout=30
    )
    response.raise_for_status()
    [container] = response.json()["template"]["containers"]
    return {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}


def test_evals():
    os.environ.update(deployed_env(os.environ["PROJECT"], os.environ["REGION"]))
    eval_set = EvalSet.model_validate_json((HERE / "requisitions.evalset.json").read_text())
    if case := os.environ.get("CASE"):
        eval_set.eval_cases = [c for c in eval_set.eval_cases if c.eval_id == case]
        assert eval_set.eval_cases, f"no case {case}"
    results = HERE / "results" / f"{datetime.now(UTC):%Y-%m-%dT%H-%M-%S}.csv"
    try:
        asyncio.run(
            AgentEvaluator.evaluate_eval_set(
                agent_module="evals.expenser_app.agent",
                eval_set=eval_set,
                eval_config=EvalConfig.model_validate_json((HERE / "test_config.json").read_text()),
                num_runs=int(os.environ.get("RUNS", "3")),
                print_detailed_results=False,
                output_file=str(results),
            )
        )
    except AssertionError:
        # A failing case isn't a failing run: the bar is on the rates below
        pass

    rows = list(csv.DictReader(results.open()))
    rates = report(rows)
    print(f"\nresults: {results}")
    low = {metric: rate for metric, rate in rates.items() if rate < BAR}
    assert not low, f"under {BAR}: {low}"


def report(rows: list[dict]) -> dict[str, float]:
    """Pass rate per metric, then which cases failed it, and which amounts passed only by rounding."""
    passed, failed = defaultdict(int), defaultdict(list)
    rounded = []
    for row in rows:
        metric, status = row["metric_name"], row["eval_status"]
        if status == "PASSED":
            passed[metric] += 1
        elif status == "FAILED":
            failed[metric].append(row["eval_id"])
        if metric == "amounts" and status == "PASSED":
            said = parse(row["actual_response"])
            if amounts_kind(json.loads(row["prompt"]), json.loads(row["expected_response"]), said) == "rounded":
                rounded.append(row["eval_id"])

    rates = {}
    print()
    for metric in sorted(passed.keys() | failed.keys()):
        total = passed[metric] + len(failed.get(metric, []))
        rates[metric] = passed[metric] / total
        print(f"{metric:20} {passed[metric]:3}/{total:<3} {rates[metric]:.0%}")
    for metric, cases in sorted(failed.items()):
        print(f"\nfailed {metric}:")
        for case, count in sorted({c: cases.count(c) for c in cases}.items()):
            print(f"  {case} ×{count}")
    if rounded:
        print(f"\nrounded: {', '.join(sorted(set(rounded)))}")
    return rates
