"""The model names each line's account, code fills in its GL code and the rest from the chart (docs/phase8/adr.md 2).

An after_model_callback, so classify, adk eval and adk web all see the whole Classification, as before.
"""

from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import ValidationError

from common import log

from .chart import BY_NAME
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
    """Each line's account, from its name, and its GL code, GL ID and type from the chart.

    The model writes names only: codes are what it slipped on (#24). A name the chart hasn't got is a rejection naming
    it, and its reason says so: we can't tell which account was meant, and never guess one (docs/phase8/adr.md 2).
    """
    lines = [line for side in ("debit", "credit") for line in said[side]]
    problems = [f"{line['name']} is not in the chart of accounts" for line in lines if not row_of(line)]
    if problems:
        log("expenser: accounts the chart can't confirm", "WARNING", problems=problems)
        return said | {
            "approve": False,
            "reason": "; ".join(problems),
            "debit": [],
            "credit": [],
            "comments": said["comments"] + problems,
        }
    return said | {side: [line_of(line) for line in said[side]] for side in ("debit", "credit")}


def row_of(line: dict) -> dict | None:
    # Case and spacing aren't a different account
    return BY_NAME.get(" ".join(line["name"].lower().split()))


def line_of(line: dict) -> dict:
    row = row_of(line)
    return {
        "name": row["Account"],
        "glCode": row["GL Code"],
        "glId": int(row["GL ID"]),
        "accountType": row["Account Type"],
        "amount": line["amount"],
    }
