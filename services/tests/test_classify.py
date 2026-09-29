"""The agent fetches its own files (docs/phase7/adr.md 3), so a fetch's status has to come back out of ADK."""

import asyncio
import os

import pytest
from fastapi import HTTPException
from google.genai import types

os.environ.setdefault("MODEL_ARMOR_TEMPLATE", "projects/p/locations/eu/templates/t")

from classify import attachments, expenser
from expenser.files import Attachments
from requisition import Requisition

REQUISITION = Requisition(
    response_number=1,
    response_id="r",
    submitted_by="a@lekkacredit.com",
    submitted_at="2026-03-06T12:40:10Z",
    payable_to="x",
    amount=1,
    files={"receipts": ["gs://ourfos-dev-attachments/x"]},
)


@pytest.mark.parametrize("status", [503, 429, 422])
def test_a_failed_fetch_keeps_its_status(monkeypatch, status):
    async def load(requisition):
        raise HTTPException(status, "receipts gs://ourfos-dev-attachments/x: cannot fetch")

    monkeypatch.setattr(attachments, "load", load)
    with pytest.raises(HTTPException) as e:
        asyncio.run(expenser.classify(REQUISITION))
    assert e.value.status_code == status
    assert "cannot fetch" in e.value.detail


def message(text):
    return types.Content(role="user", parts=[types.Part(text=text)])


def test_the_plugin_puts_the_files_in_the_turn(monkeypatch):
    async def load(requisition):
        return [{"field": "receipts", "mimeType": "application/pdf", "data": b"%PDF-1.4"}]

    monkeypatch.setattr(attachments, "load", load)
    got = asyncio.run(
        Attachments().on_user_message_callback(
            invocation_context=None, user_message=message(REQUISITION.model_dump_json())
        )
    )
    assert [p.text for p in got.parts[1:2]] == ["receipts"]
    assert got.parts[2].inline_data.mime_type == "application/pdf"


def test_anything_else_is_left_alone():
    got = asyncio.run(Attachments().on_user_message_callback(invocation_context=None, user_message=message("hello")))
    assert got is None
