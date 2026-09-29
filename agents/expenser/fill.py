"""The model names each line's account, code fills in the rest from the chart (docs/phase8/adr.md 2).

An after_model_callback, so classify, adk eval and adk web all see the whole Classification, as before.
"""

from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import ValidationError

from common import log

from .chart import BY_CODE
from .schema import Answer, Classification


async def fill(*, callback_context, llm_response: LlmResponse) -> LlmResponse | None:
    text = "".join(p.text or "" for p in (llm_response.content.parts if llm_response.content else []) if not p.thought)
    # The model's answer, in the shape the model writes. Anything else, e.g. Model Armor's block, is left alone
    try:
        said = Answer.model_validate_json(text)
    except ValidationError:
        return None
    classification = Classification.model_validate(whole(said.model_dump()))
    content = types.Content(role="model", parts=[types.Part(text=classification.model_dump_json())])
    return llm_response.model_copy(update={"content": content})


def whole(said: dict) -> dict:
    """Each line's name, glId and accountType from the chart.

    A line the chart can't confirm is a rejection naming it: a code the chart hasn't got, or one whose name isn't the
    one the model wrote. The model's name is its check on its code, and a person picks which it meant.
    """
    lines = [line for side in ("debit", "credit") for line in said[side]]
    problems = [problem(line) for line in lines if problem(line)]
    if problems:
        log("expenser: accounts the chart can't confirm", "WARNING", problems=problems)
        return said | {"approve": False, "debit": [], "credit": [], "comments": said["comments"] + problems}
    return said | {side: [line_of(line) for line in said[side]] for side in ("debit", "credit")}


def problem(line: dict) -> str | None:
    row = BY_CODE.get(line["glCode"])
    if not row:
        return f"GL code {line['glCode']} is not in the chart of accounts"
    if same(line["name"]) != same(row["Account"]):
        return f"GL code {line['glCode']} is {row['Account']} in the chart, not {line['name']}"
    return None


def same(name: str) -> str:
    # Case and spacing aren't a different account
    return " ".join(name.lower().split())


def line_of(line: dict) -> dict:
    row = BY_CODE[line["glCode"]]
    return {
        "name": row["Account"],
        "glCode": line["glCode"],
        "glId": int(row["GL ID"]),
        "accountType": row["Account Type"],
        "amount": line["amount"],
    }
