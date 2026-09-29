"""glId is a lookup, not a judgement (docs/phase7/adr.md 5, docs/phase8/adr.md 2): the model names the account, code
fills in its GL ID and type from the chart."""

import asyncio
import json
import os
import re

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from expenser.chart import BY_CODE, ROWS, shown
from expenser.fill import fill
from expenser.prompt import PROMPT
from expenser.schema import Classification

GL_IDS = {row["GL Code"]: int(row["GL ID"]) for row in ROWS}


def test_each_gl_code_is_one_account():
    assert len(GL_IDS) == len(ROWS)
    assert len(set(GL_IDS.values())) == len(ROWS)


def test_the_model_sees_no_gl_ids():
    assert shown().splitlines()[0] == "Account,GL Code,Account Type,Comment"
    assert "GL ID" not in PROMPT


def test_the_prompt_s_examples_are_in_the_chart():
    lines = re.findall(r'"name": "([^"]+)", "glCode": "(\d+)"', PROMPT)
    assert lines
    assert all(BY_CODE[code]["Account"] == name for name, code in lines)


def test_the_stub_matches_the_chart():
    from routers.requisitions import stub

    classification = stub(10, "stub")
    for line in classification["debit"] + classification["credit"]:
        assert GL_IDS[line["glCode"]] == line["glId"]


def answer(debit_code="5020", name="Advertising and Promotions"):
    said = {
        "approve": True,
        "reason": "Parking",
        "debit": [{"name": name, "glCode": debit_code, "amount": 3.0}],
        "credit": [{"name": "Cash at Vault", "glCode": "10000000", "amount": 3.0}],
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


def test_the_chart_s_name_is_stored(capsys):
    got = filled(answer(name="Parking"))
    assert got.debit[0].name == "Advertising and Promotions"
    assert "name differs" in capsys.readouterr().out


def test_an_account_not_in_the_chart_is_a_rejection():
    got = filled(answer(debit_code="1812"))
    assert not got.approve
    assert got.debit == got.credit == []
    assert "GL code 1812 is not in the chart of accounts" in got.comments


def test_anything_else_is_left_alone():
    blocked = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Blocked by Model Armor")]))
    assert asyncio.run(fill(callback_context=None, llm_response=blocked)) is None
