"""Which cases failed which metric, and what the runs cost, read from the results `adk eval` keeps. Nothing is scored here.

python3 agents/expenser/evals/report.py [RUNS]    the last RUNS results, 1 by default
"""

import json
import sys
from collections import Counter
from pathlib import Path

HISTORY = Path(__file__).parents[1] / ".adk/eval_history"
PASSED, FAILED = 1, 2  # ADK's EvalStatus

# gemini-3.5-flash-lite, dollars per million tokens (docs/phase8/tdd.md)
INPUT, CACHED, OUTPUT = 0.30, 0.03, 2.50


def usages(case: dict) -> list[dict]:
    """The model's usage_metadata, once per call: every metric repeats the same invocations, so the first is read."""
    first = next(iter(case["eval_metric_result_per_invocation"]), None)
    events = first["actual_invocation"]["intermediate_data"]["invocation_events"] if first else []
    return [e["usage_metadata"] for e in events if e.get("usage_metadata")]


def cost(calls: list[dict]) -> str:
    def total(key):
        return sum(u.get(key) or 0 for u in calls)

    def modality(name):
        return sum(
            d["token_count"] for u in calls for d in u.get("prompt_tokens_details") or [] if d["modality"] == name
        )

    prompt, cached, out = (
        total("prompt_token_count"),
        total("cached_content_token_count"),
        total("candidates_token_count"),
    )
    out += total("thoughts_token_count")
    dollars = ((prompt - cached) * INPUT + cached * CACHED + out * OUTPUT) / 1e6
    n = len(calls) or 1
    return (
        f"{len(calls)} calls, ${dollars:.4f}, ${dollars / n:.5f} a call. Per call: "
        f"text {modality('TEXT') // n}, images {modality('IMAGE') // n}, documents {modality('DOCUMENT') // n}, "
        f"cached {cached // n}, output {out // n} tokens"
    )


runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
files = sorted(HISTORY.glob("*.evalset_result.json"), key=lambda p: p.stat().st_mtime)[-runs:]
cases = [case for f in files for case in json.loads(f.read_text())["eval_case_results"]]
failed = Counter(
    (metric["metric_name"], case["eval_id"])
    for case in cases
    for metric in case["overall_eval_metric_results"]
    if metric["eval_status"] == FAILED
)

print(f"{sum(case['final_eval_status'] == PASSED for case in cases)} of {len(cases)} case runs passed")
for (metric, eval_id), times in sorted(failed.items()):
    print(f"  {metric}: {eval_id}" + (f" ×{times}" if times > 1 else ""))
print(cost([u for case in cases for u in usages(case)]))
