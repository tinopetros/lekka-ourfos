"""Model Armor, field by field and file by file, as well as whole.

Inside a whole requisition's JSON, Model Armor misses an injection it catches in the free-text field on its own
(phase 5 ADR 12). So payable_to and comment are screened alone first. The plugin's whole-prompt screen reads only
text, so PDFs are screened alone too (phase 6 ADR 5). Images aren't: Model Armor fails on them. Nor are PDFs over
Model Armor's 4 MB. Then the whole prompt, as before. Leans on the plugin's private helpers, so it moves with the
pinned ADK version.
"""

import json
import logging

from google.adk.integrations.model_armor import ModelArmorPlugin
from google.cloud import modelarmor_v1

FREE_TEXT = ("payable_to", "comment")
DOCUMENTS = {"application/pdf": modelarmor_v1.ByteDataItem.ByteItemType.PDF}
# Model Armor refuses files outside these, and failing closed would hand over a clean requisition
SCREENABLE_BYTES = range(69, 4 * 1024 * 1024 + 1)

logger = logging.getLogger(__name__)


class FieldsModelArmorPlugin(ModelArmorPlugin):
    async def before_model_callback(self, *, callback_context, llm_request):
        template = self._config.prompt_template_name
        items = [modelarmor_v1.DataItem(text=text) for text in free_text(llm_request)] + documents(llm_request)
        # One at a time: concurrent first calls on a cold client failed, and failing closed blocked a clean run
        for item in items:
            try:
                response = await self.client.sanitize_user_prompt(
                    request=modelarmor_v1.SanitizeUserPromptRequest(name=template, user_prompt_data=item)
                )
            except Exception:  # fails closed, as the plugin does
                logger.exception("Model Armor screening failed", extra={"file": bool(item.byte_item)})
                return self._handle_screening_failure(self._config.input_blocked_message)
            blocked = self._handle_sanitization_result(
                response.sanitization_result, direction="input", blocked_message=self._config.input_blocked_message
            )
            if blocked:
                return blocked
        return await super().before_model_callback(callback_context=callback_context, llm_request=llm_request)


def latest_user_turn(llm_request):
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            return content
    return None


def free_text(llm_request) -> list[str]:
    """The latest user turn's free-text fields, when it's a requisition. Anything else is screened whole only."""
    turn = latest_user_turn(llm_request)
    # The requisition is the turn's first part. Files and their labels follow it
    first = next((part.text for part in (turn.parts or []) if part.text), None) if turn else None
    try:
        requisition = json.loads(first or "")
    except ValueError:
        return []
    if not isinstance(requisition, dict):
        return []
    return [str(requisition[key]) for key in FREE_TEXT if requisition.get(key)]


def documents(llm_request) -> list[modelarmor_v1.DataItem]:
    """The latest user turn's files Model Armor can read. Images, and PDFs over 4 MB, pass unscreened."""
    turn = latest_user_turn(llm_request)
    items = []
    for part in (turn.parts or []) if turn else []:
        if not (part.inline_data and part.inline_data.mime_type in DOCUMENTS):
            continue
        if len(part.inline_data.data) not in SCREENABLE_BYTES:
            logger.warning("PDF not screened: %d bytes, outside Model Armor's limits", len(part.inline_data.data))
            continue
        items.append(
            modelarmor_v1.DataItem(
                byte_item=modelarmor_v1.ByteDataItem(
                    byte_data_type=DOCUMENTS[part.inline_data.mime_type], byte_data=part.inline_data.data
                )
            )
        )
    return items
