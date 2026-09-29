"""Expenser: a requisition in, a classification out, with ourfos-v2's prompt."""

import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.integrations.model_armor import ModelArmorConfig

from .files import Attachments
from .fill import fill
from .prompt import PROMPT
from .schema import Answer, Classification  # noqa: F401  classify reads the whole Classification from here
from .screen import FieldsModelArmorPlugin

root_agent = Agent(
    name="expenser",
    model=os.environ.get("EXPENSER_MODEL", "gemini-3.5-flash-lite"),
    description="Classifies a requisition into an approval and journal lines.",
    # A function, so ADK doesn't read the examples' braces as session state
    instruction=lambda _: PROMPT,
    # The model names each line's account; fill looks up the rest, so what comes out is a whole Classification
    output_schema=Answer,
    after_model_callback=fill,
)

# Fetches the requisition's files, then screens every prompt before the model sees it, its free text alone too.
# Fails closed on a match and on an error
app = App(
    name="expenser",
    root_agent=root_agent,
    plugins=[
        Attachments(),
        FieldsModelArmorPlugin(config=ModelArmorConfig(prompt_template_name=os.environ["MODEL_ARMOR_TEMPLATE"])),
    ],
)
