import json

from fastapi import HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors, types

from expenser.agent import Classification, app


async def classify(requisition: dict) -> dict:
    """One requisition in, the stub's shape out. Maps what goes wrong to what the workflow retries (TDD, Errors)."""
    # A session service per request, so sessions never pile up on a warm instance (ADR 3)
    runner = Runner(app=app, session_service=InMemorySessionService(), auto_create_session=True)
    message = types.Content(role="user", parts=[types.Part(text=json.dumps(requisition))])
    final = None
    try:
        async for event in runner.run_async(user_id="classify", session_id="classify", new_message=message):
            if event.is_final_response():
                final = event
    except errors.APIError as e:
        # 429 and 503 are retried by the workflow, anything else hands over
        raise HTTPException(e.code if e.code in (429, 503) else 500, f"expenser: {e.code}") from e

    if final and (final.custom_metadata or {}).get("model_armor_blocked"):
        raise HTTPException(422, "expenser: blocked by Model Armor")
    text = final.content.parts[0].text if final and final.content and final.content.parts else ""
    return Classification.model_validate_json(text).model_dump()
