"""A requisition's files, fetched and shown to the model (docs/phase7/adr.md 3).

The plugin reads the requisition from the user's message, fetches its files through services' `classify.attachments`,
and puts them in the turn. So classify, `adk eval` and `adk web` all hand the agent the same thing: the requisition.
"""

import json

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types
from pydantic import ValidationError

from classify import attachments
from requisition import Requisition


class Attachments(BasePlugin):
    """Before Model Armor and the model: the requisition's refs become its files. A fetch that fails raises."""

    def __init__(self):
        super().__init__(name="attachments")

    async def on_user_message_callback(
        self, *, invocation_context: InvocationContext, user_message: types.Content
    ) -> types.Content | None:
        text = next((part.text for part in user_message.parts or [] if part.text), "")
        try:
            requisition = Requisition.model_validate_json(text)
        except ValidationError:
            # Not a requisition, e.g. a question typed into adk web: left as it is
            return None
        return turn(requisition, await attachments.load(requisition))


def turn(requisition: Requisition, files: list[dict]) -> types.Content:
    """The requisition as JSON first, then each file after a label naming its form field."""
    parts = [types.Part(text=json.dumps(requisition.to_json()))]
    for f in files:
        parts.append(types.Part(text=f["field"]))
        parts.append(types.Part.from_bytes(data=f["data"], mime_type=f["mimeType"]))
    return types.Content(role="user", parts=parts)
