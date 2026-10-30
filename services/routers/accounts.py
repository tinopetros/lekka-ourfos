"""The accounts a correction can post to, read from Mifos for ourfos-api, which keeps no Mifos credentials of its own."""

import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from expenser.chart import ROWS
from integrations import mifos

router = APIRouter(prefix="/mifos")

# What expenser picks from: first in the picker, as the likeliest
EXPENSER = {int(row["GL ID"]) for row in ROWS}


@router.get("/accounts")
async def accounts(tenant: str | None = None):
    """This environment's tenant, unless asked for the test runs', and no other"""
    tenant = tenant or os.environ["MIFOS_TENANT_ID"]
    if tenant not in (os.environ["MIFOS_TENANT_ID"], mifos.TEST_TENANT):
        raise HTTPException(422, f"No accounts for tenant {tenant} here")
    found = await run_in_threadpool(mifos.accounts, tenant)
    return [{**a, "expenser": a["glId"] in EXPENSER} for a in found]
