"""Expenser as prod runs it, plus one plugin that fetches a requisition's files (docs/phase7/adr.md 3).

Never deployed: the deployed agent is handed its files by classify, and never fetches.
"""

from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from classify import attachments
from classify.expenser import turn
from expenser.agent import app as expenser
from requisition import Requisition


class Attachments(BasePlugin):
    """The eval case's requisition, with gs:// refs, into the turn classify would give the model: same bytes, labels, order."""

    def __init__(self):
        super().__init__(name="attachments")

    async def on_user_message_callback(
        self, *, invocation_context: InvocationContext, user_message: types.Content
    ) -> types.Content:
        requisition = Requisition.model_validate_json(user_message.parts[0].text)
        return turn(requisition, await attachments.load(requisition))


root_agent = expenser.root_agent
# Fetched first, so Model Armor screens what the model will see, as in prod
app = App(name="expenser", root_agent=root_agent, plugins=[Attachments(), *expenser.plugins])
