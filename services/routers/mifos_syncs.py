"""What the mifos-sync workflow calls each night, one kind a run: clients, loans."""

from fastapi import APIRouter

import mifos_sync

router = APIRouter(prefix="/mifos-sync")


@router.post("/{kind}")
def run(kind: str):
    return mifos_sync.run(kind)
