import json

from fastapi import HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors, types

from common import RETRIED
from expenser.agent import Classification, app
from requisition import Requisition


def turn(requisition: Requisition, files: list[dict]) -> types.Content:
    """The requisition as JSON first, then each file after a label naming its form field."""
    parts = [types.Part(text=json.dumps(requisition.to_json()))]
    for f in files:
        parts.append(types.Part(text=f["field"]))
        parts.append(types.Part.from_bytes(data=f["data"], mime_type=f["mimeType"]))
    return types.Content(role="user", parts=parts)


async def classify(requisition: Requisition, files: list[dict]) -> dict:
    """One requisition and its files in, the stub's shape out, with failures as statuses the workflow retries or hands over."""
    # Its own session service, so sessions never pile up on a warm instance
    runner = Runner(app=app, session_service=InMemorySessionService(), auto_create_session=True)
    message = turn(requisition, files)
    final = None
    try:
        async for event in runner.run_async(user_id="classify", session_id="classify", new_message=message):
            if event.is_final_response():
                final = event
    except errors.APIError as e:
        # What the workflow retries passes through (is_transient), anything else hands over
        raise HTTPException(e.code if e.code in RETRIED else 500, f"expenser: {e.code}") from e

    if final and (final.custom_metadata or {}).get("model_armor_blocked"):
        raise HTTPException(422, "expenser: blocked by Model Armor")
    text = final.content.parts[0].text if final and final.content and final.content.parts else ""
    return Classification.model_validate_json(text).model_dump()
