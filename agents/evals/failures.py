"""Which cases failed which metric, read from the results `adk eval` keeps. Nothing is scored here.

python3 agents/evals/failures.py [RUNS]    the last RUNS results, 1 by default
"""

import json
import sys
from collections import Counter
from pathlib import Path

HISTORY = Path(__file__).parents[1] / "expenser/.adk/eval_history"
PASSED, FAILED = 1, 2  # ADK's EvalStatus

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
