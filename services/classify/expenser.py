import json

from fastapi import HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors, types

from common import RETRIED
from expenser.agent import Classification, app
from requisition import Requisition


async def classify(requisition: Requisition) -> dict:
    """One requisition in, the stub's shape out, with failures as statuses the workflow retries or hands over.

    The agent's own plugin fetches the files (docs/phase7/adr.md 3), so the message is the requisition alone.
    """
    # Its own session service, so sessions never pile up on a warm instance
    runner = Runner(app=app, session_service=InMemorySessionService(), auto_create_session=True)
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(requisition.to_json()))])
    final = None
    try:
        async for event in runner.run_async(user_id="classify", session_id="classify", new_message=message):
            if event.is_final_response():
                final = event
    except RuntimeError as e:
        # ADK wraps what a plugin raises. A fetch's HTTPException is ours, with the status the workflow acts on
        if isinstance(e.__cause__, HTTPException):
            raise e.__cause__ from None
        raise
    except errors.APIError as e:
        # What the workflow retries passes through (is_transient), anything else hands over
        raise HTTPException(e.code if e.code in RETRIED else 500, f"expenser: {e.code}") from e

    if final and (final.custom_metadata or {}).get("model_armor_blocked"):
        raise HTTPException(422, "expenser: blocked by Model Armor")
    text = final.content.parts[0].text if final and final.content and final.content.parts else ""
    return Classification.model_validate_json(text).model_dump()
