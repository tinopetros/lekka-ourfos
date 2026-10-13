"""glId is a lookup, not a judgement (docs/phase7/adr.md 5, docs/phase8/adr.md 2): the model names the account, code
fills in its GL code, GL ID and type from the chart (#25)."""

import asyncio
import json
import os
import re

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from expenser.chart import BY_NAME, ROWS, shown
from expenser.fill import fill
from expenser.prompt import PROMPT
from expenser.schema import Classification

GL_IDS = {row["GL Code"]: int(row["GL ID"]) for row in ROWS}


def test_each_gl_code_is_one_account():
    assert len(GL_IDS) == len(ROWS)
    assert len(set(GL_IDS.values())) == len(ROWS)


def test_each_name_is_one_account():
    assert len(BY_NAME) == len(ROWS)


def test_the_model_sees_no_codes_or_ids():
    assert shown().splitlines()[0] == "Account,Account Type,Comment"
    assert "GL ID" not in PROMPT and "glCode" not in PROMPT


def test_the_prompt_s_examples_are_in_the_chart():
    names = re.findall(r'"name": "([^"]+)"', PROMPT)
    assert names
    assert all(" ".join(name.lower().split()) in BY_NAME for name in names)


def test_the_stub_matches_the_chart():
    from routers.requisitions import stub

    classification = stub(10, "stub")
    for line in classification["debit"] + classification["credit"]:
        assert GL_IDS[line["glCode"]] == line["glId"]


def answer(name="Advertising and Promotions"):
    said = {
        "approve": True,
        "reason": "Parking",
        "debit": [{"name": name, "amount": 3.0}],
        "credit": [{"name": "Cash at Vault", "amount": 3.0}],
        "comments": ["Signed"],
    }
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=json.dumps(said))]))


def filled(response):
    got = asyncio.run(fill(callback_context=None, llm_response=response))
    return Classification.model_validate_json(got.content.parts[0].text)


def test_fill_looks_up_each_line():
    got = filled(answer())
    assert got.approve
    assert [(line.glCode, line.glId, line.accountType) for line in got.debit + got.credit] == [
        ("5020", 66, "EXPENSE"),
        ("10000000", 109, "ASSET"),
    ]


def test_the_chart_s_name_is_stored():
    assert filled(answer(name="advertising and  promotions")).debit[0].name == "Advertising and Promotions"


def test_a_name_the_chart_hasn_t_got_is_a_rejection_that_says_why():
    got = filled(answer(name="Coffee for the office"))
    assert not got.approve
    assert got.debit == got.credit == []
    assert got.reason == "Coffee for the office is not in the chart of accounts"
    assert got.reason in got.comments
