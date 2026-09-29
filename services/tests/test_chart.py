"""glId is a lookup, not a judgement (docs/phase7/adr.md 5): every glCode we name must carry its glId from the chart."""

import csv
import re

from expenser.prompt import ACCOUNTS, PROMPT

CHART = list(csv.DictReader(ACCOUNTS.splitlines()))
GL_IDS = {row["GL Code"]: int(row["GL ID"]) for row in CHART}


def test_each_gl_code_is_one_account():
    assert len(GL_IDS) == len(CHART)
    assert len(set(GL_IDS.values())) == len(CHART)


def test_the_prompt_s_examples_match_the_chart():
    lines = re.findall(r'"glCode": "(\d+)", "glId": (\d+)', PROMPT)
    assert lines
    assert {code: int(gl_id) for code, gl_id in lines}.items() <= GL_IDS.items()


def test_the_stub_matches_the_chart():
    from routers.requisitions import stub

    classification = stub(10, "stub")
    for line in classification["debit"] + classification["credit"]:
        assert GL_IDS[line["glCode"]] == line["glId"]
