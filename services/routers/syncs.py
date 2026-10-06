"""What the sync workflow calls each night, or by hand with a date for the preload (docs/phase12/tdd.md, step 6).
One route per kind: clients and loans can follow journal entries."""

from fastapi import APIRouter, HTTPException

import sync

router = APIRouter(prefix="/sync")

KINDS = {sync.KIND: sync.journal_entries}


@router.post("/{kind}")
def run(kind: str, body: dict):
    if kind not in KINDS:
        raise HTTPException(404, f"no sync for {kind}")
    return KINDS[kind](body.get("from"))
