"""Model Armor, field by field as well as whole.

Inside a whole requisition's JSON, Model Armor misses an injection it catches in the free-text field on its own
(phase 5 ADR 12). So payable_to and comment are screened alone first, then the whole prompt as before.
Leans on the plugin's private helpers, so it moves with the pinned ADK version.
"""

import json
import logging

from google.adk.integrations.model_armor import ModelArmorPlugin

FREE_TEXT = ("payable_to", "comment")

logger = logging.getLogger(__name__)


class FieldsModelArmorPlugin(ModelArmorPlugin):
    async def before_model_callback(self, *, callback_context, llm_request):
        template = self._config.prompt_template_name
        # One at a time: concurrent first calls on a cold client failed, and failing closed blocked a clean run
        for text in free_text(llm_request):
            try:
                result = await self._sanitize_user_prompt(text, template)
            except Exception:  # fails closed, as the plugin does
                logger.exception("Model Armor field screening failed")
                return self._handle_screening_failure(self._config.input_blocked_message)
            blocked = self._handle_sanitization_result(
                result, direction="input", blocked_message=self._config.input_blocked_message
            )
            if blocked:
                return blocked
        return await super().before_model_callback(callback_context=callback_context, llm_request=llm_request)


def free_text(llm_request) -> list[str]:
    """The latest user turn's free-text fields, when it's a requisition. Anything else is screened whole only."""
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            # The requisition is the turn's first part. Files and their labels follow it
            text = next((part.text for part in content.parts or [] if part.text), "")
            try:
                requisition = json.loads(text)
            except ValueError:
                return []
            if not isinstance(requisition, dict):
                return []
            return [str(requisition[key]) for key in FREE_TEXT if requisition.get(key)]
    return []
