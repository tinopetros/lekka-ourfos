"""Expenser's evals, scored (docs/phase7/tdd.md, The metrics). Each is 1 or 0 per invocation, and deterministic."""

import json
from collections import defaultdict

from google.adk.evaluation.eval_metrics import EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

CENT = 0.01


def text(content) -> str:
    return "".join(part.text or "" for part in (content.parts if content else []) if part.text)


def answer(content) -> dict:
    return parse(text(content))


def parse(said: str) -> dict:
    """What the model said. Blocked, empty or unreadable is a handover, so not an approval."""
    try:
        return json.loads(said)
    except ValueError:
        return {"approve": False}


def by_account(lines: list[dict]) -> dict[str, float]:
    """Summed per glCode, so splitting or lumping lines doesn't matter."""
    sums = defaultdict(float)
    for line in lines:
        sums[str(line["glCode"])] += float(line["amount"])
    return dict(sums)


def amounts_kind(requisition: dict, expected: dict, actual: dict) -> str:
    """exact, rounded or wrong. Rounded: posted the form's amount, each account within the form's gap from the ledger."""
    sides = ("debit", "credit")
    want = {side: by_account(expected[side]) for side in sides}
    got = {side: by_account(actual.get(side, [])) for side in sides}
    if any(want[side].keys() != got[side].keys() for side in sides):
        return "wrong"
    if all(abs(got[s][code] - want[s][code]) <= CENT for s in sides for code in want[s]):
        return "exact"
    gap = abs(requisition["amount"] - sum(want["debit"].values()))
    rounded = gap > CENT and all(
        abs(sum(got[s].values()) - requisition["amount"]) <= CENT
        and all(abs(got[s][code] - want[s][code]) <= gap + CENT for code in want[s])
        for s in sides
    )
    return "rounded" if rounded else "wrong"


def score(judge):
    """One invocation's judgement, 1, 0 or None (not evaluated), into ADK's result."""

    def metric(eval_metric, actual_invocations, expected_invocations, conversation_scenario=None) -> EvaluationResult:
        results = []
        for actual, expected in zip(actual_invocations, expected_invocations or [], strict=True):
            requisition = json.loads(text(expected.user_content))
            value = judge(requisition, answer(expected.final_response), answer(actual.final_response))
            status = EvalStatus.NOT_EVALUATED if value is None else EvalStatus.PASSED if value else EvalStatus.FAILED
            results.append(
                PerInvocationResult(
                    actual_invocation=actual, expected_invocation=expected, score=value, eval_status=status
                )
            )
        scored = [r.score for r in results if r.score is not None]
        if not scored:
            return EvaluationResult(per_invocation_results=results)
        overall = sum(scored) / len(scored)
        return EvaluationResult(
            overall_score=overall,
            overall_eval_status=EvalStatus.PASSED if overall == 1 else EvalStatus.FAILED,
            per_invocation_results=results,
        )

    metric.__name__ = judge.__name__
    return metric


def both_approve(expected: dict, actual: dict) -> bool:
    return bool(expected["approve"] and actual.get("approve"))


@score
def no_false_approval(requisition, expected, actual):
    """Approved what should be rejected: the dangerous one."""
    return 0.0 if actual.get("approve") and not expected["approve"] else 1.0


@score
def accounts(requisition, expected, actual):
    if not both_approve(expected, actual):
        return None
    same = all(by_account(expected[s]).keys() == by_account(actual.get(s, [])).keys() for s in ("debit", "credit"))
    return 1.0 if same else 0.0


@score
def amounts(requisition, expected, actual):
    if not both_approve(expected, actual):
        return None
    return 0.0 if amounts_kind(requisition, expected, actual) == "wrong" else 1.0


@score
def no_false_rejection(requisition, expected, actual):
    """Rejected what should be approved: a handover, not money."""
    return 0.0 if expected["approve"] and not actual.get("approve") else 1.0
