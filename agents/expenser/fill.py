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
    """Each line's name, glId and accountType from the chart. An account the chart hasn't got is a rejection naming it."""
    unknown = [line["glCode"] for side in ("debit", "credit") for line in said[side] if line["glCode"] not in BY_CODE]
    if unknown:
        log("expenser: account not in the chart", "WARNING", glCodes=unknown)
        return said | {
            "approve": False,
            "debit": [],
            "credit": [],
            "comments": said["comments"] + [f"GL code {code} is not in the chart of accounts" for code in unknown],
        }
    return said | {side: [line_of(line) for line in said[side]] for side in ("debit", "credit")}


def line_of(line: dict) -> dict:
    row = BY_CODE[line["glCode"]]
    if line["name"] != row["Account"]:
        # The model's name is its check on the code. The code is what's posted, so it wins, and a mismatch is logged
        log("expenser: account name differs from the chart", "WARNING", said=line["name"], glCode=line["glCode"])
    return {
        "name": row["Account"],
        "glCode": line["glCode"],
        "glId": int(row["GL ID"]),
        "accountType": row["Account Type"],
        "amount": line["amount"],
    }
