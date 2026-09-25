"""Expenser: a requisition in, a classification out. The prompt is a dummy for now (phase 3)."""

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.integrations.model_armor import ModelArmorConfig, ModelArmorPlugin
from pydantic import BaseModel


class Line(BaseModel):
    glCode: str
    amount: float


# The stub's shape, so the workflow can't tell a model answered
class Classification(BaseModel):
    approve: bool
    reason: str
    debit: list[Line]
    credit: list[Line]


root_agent = Agent(
    name="expenser",
    model=os.environ.get("EXPENSER_MODEL", "gemini-3.5-flash-lite"),
    description="Classifies a requisition into an approval and journal lines.",
    instruction=(
        "You get a requisition as JSON. Reject it if its amount is over 10000, with reason 'Too large'. "
        "Otherwise approve it, with a one-line reason. "
        "Either way, debit glCode 6100 and credit glCode 1100, each for exactly the amount."
    ),
    output_schema=Classification,
)

# Screens every prompt before the model sees it. Fails closed on a match and on an error
app = App(
    name="expenser",
    root_agent=root_agent,
    plugins=[ModelArmorPlugin(config=ModelArmorConfig(prompt_template_name=os.environ["MODEL_ARMOR_TEMPLATE"]))],
)
