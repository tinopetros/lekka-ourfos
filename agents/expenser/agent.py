"""Expenser: a requisition in, a classification out, with ourfos-v2's prompt."""

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.integrations.model_armor import ModelArmorConfig
from pydantic import BaseModel

from .prompt import PROMPT
from .screen import FieldsModelArmorPlugin


class Line(BaseModel):
    name: str
    glCode: str
    # What Mifos posts to. glCode is what a person reads
    glId: int
    accountType: str
    amount: float


# The stub answers in this shape too, so the workflow can't tell a model answered
class Classification(BaseModel):
    approve: bool
    reason: str
    debit: list[Line]
    credit: list[Line]
    comments: list[str]


root_agent = Agent(
    name="expenser",
    model=os.environ.get("EXPENSER_MODEL", "gemini-3.5-flash-lite"),
    description="Classifies a requisition into an approval and journal lines.",
    # A function, so ADK doesn't read the examples' braces as session state
    instruction=lambda _: PROMPT,
    output_schema=Classification,
)

# Screens every prompt before the model sees it, its free text alone too. Fails closed on a match and on an error
app = App(
    name="expenser",
    root_agent=root_agent,
    plugins=[FieldsModelArmorPlugin(config=ModelArmorConfig(prompt_template_name=os.environ["MODEL_ARMOR_TEMPLATE"]))],
)
