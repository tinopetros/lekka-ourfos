"""Mifos, through our connector (docs/phase11/tdd.md). Dicts in and out, failures as HTTP statuses.

Dev posts to the demo tenant, prod to default: the books. A fixture's simulate, dev only, keeps phase 5's stub.
"""

import os
import uuid
from datetime import UTC, date, datetime, timedelta
from functools import cache

import httpx
from fastapi import HTTPException
from mifos_connector import MifosApiError, MifosClient, MifosError, MifosNetworkError

from common import log, simulate

BOOKS = "default"
STUB = "stub-txn-"
# Under call_service's 20s, so a slow Mifos is ours to call uncertain, not the workflow's
TIMEOUT = 15


@cache
def client() -> MifosClient:
    tenant = os.environ["MIFOS_TENANT_ID"]
    # Terraform refuses this too, and dev's user doesn't exist in the books (docs/phase11/adr.md 4)
    if tenant == BOOKS and os.environ.get("GOOGLE_CLOUD_PROJECT") != "ourfos-prod":
        raise HTTPException(500, "only ourfos-prod posts to Mifos's default tenant")
    return MifosClient(
        base_url=os.environ["MIFOS_BASE_URL"],
        username=os.environ["MIFOS_USERNAME"],
        password=os.environ["MIFOS_PASSWORD"],
        tenant_id=tenant,
        timeout_seconds=TIMEOUT,
        verify_ssl=os.environ.get("MIFOS_VERIFY_SSL", "true") != "false",
    )


def connect():
    """One read when an instance starts: Mifos answers, and our user logs in. Logged, never raised (step 3)"""
    tenant = os.environ.get("MIFOS_TENANT_ID")
    try:
        # Today's manual entries only: a read with no range would make Mifos scan all of them
        manual_entries(datetime.now(UTC).date(), {"limit": 1})
        log("mifos connected", tenant=tenant)
    except (MifosError, HTTPException, KeyError) as e:
        log(f"mifos not connected: {e!r}", "ERROR", tenant=tenant)


def post(reference: str, debit: list, credit: list, on: date, comments: str, code=None) -> dict:
    # Logged before posting, so a timeout looks like a post that landed but answered late.
    # Counting these lines per execution is how we prove a timeout never posts twice
    log("mifos post", reference=reference, debit=debit, credit=credit, on=on, stub=bool(code))
    if code:
        simulate("mifos_post", code)
        # Its own each time: a correction posts twice under one reference
        return {"mifos_transaction_id": f"{STUB}{uuid.uuid4().hex[:13]}"}
    try:
        posted = client().journal_entries.create(
            {
                "officeId": int(os.environ.get("MIFOS_OFFICE_ID", "1")),
                "currencyCode": os.environ.get("MIFOS_CURRENCY", "USD"),
                "transactionDate": on.isoformat(),
                "dateFormat": "yyyy-MM-dd",
                "locale": "en",
                "referenceNumber": reference,
                "comments": comments,
                "debits": [{"glAccountId": d["glId"], "amount": d["amount"]} for d in debit],
                "credits": [{"glAccountId": c["glId"], "amount": c["amount"]} for c in credit],
            }
        )
    except MifosError as e:
        raise failed(e, reference) from e
    log("mifos posted", reference=reference, mifos_transaction_id=posted["transactionId"])
    return {"mifos_transaction_id": posted["transactionId"]}


def failed(e: MifosError, reference: str) -> HTTPException:
    """Only what certainly didn't land is said so. Anything else may have, and the workflow hands it over as such"""
    if isinstance(e, MifosApiError) and e.status_code < 500:
        return HTTPException(422, f"Mifos refused it, so nothing was posted. {e}")
    if isinstance(e, MifosNetworkError) and isinstance(e.cause, (httpx.ConnectError, httpx.ConnectTimeout)):
        return HTTPException(503, "Mifos couldn't be reached, so nothing was posted")
    log("mifos post uncertain", "ERROR", reference=reference, error=str(e))
    return HTTPException(504, f"Mifos didn't confirm the post: {e}")


def read(mifos_transaction_id: str) -> dict:
    """One transaction as Mifos has it, in our record's shape"""
    try:
        lines = client().journal_entries.list_all({"transactionId": mifos_transaction_id, "manualEntriesOnly": True})
    except MifosError as e:
        raise read_failed(e) from e
    return entry(mifos_transaction_id, lines)


def manual_entries(since: date, params: dict) -> list:
    """A page of Mifos's manual journal entries, its lines that is, booked since then. Always manual and always a range:
    Mifos has hundreds of thousands of entries, most of them loans' and savings' own"""
    # A year ahead: an entry can be booked in the future
    until = (datetime.now(UTC) + timedelta(days=366)).date()
    window = {"fromDate": since.isoformat(), "toDate": until.isoformat(), "dateFormat": "yyyy-MM-dd", "locale": "en"}
    try:
        return client().journal_entries.list({**params, **window, "manualEntriesOnly": True})["pageItems"]
    except MifosError as e:
        raise read_failed(e) from e


def ours() -> str:
    """Our Mifos user, whose entries the step that posts records"""
    return os.environ["MIFOS_USERNAME"]


def read_failed(e: MifosError) -> HTTPException:
    # A read, so the workflow may retry it
    status = e.status_code if isinstance(e, MifosApiError) else 503
    return HTTPException(503 if status >= 500 else 500, f"mifos read: {e}")


def entry(mifos_transaction_id: str, lines: list) -> dict:
    """Mifos's lines of one transaction, as one entry. What's on every line is kept once, from the first."""
    first = lines[0] if lines else {}
    return {
        "transaction_id": mifos_transaction_id,
        "transaction_date": day(first.get("transactionDate")),
        "created_on": day(first.get("createdDate")),
        "office": {"id": first.get("officeId"), "name": first.get("officeName")},
        "currency": (first.get("currency") or {}).get("code"),
        "reference_number": first.get("referenceNumber"),
        "comments": first.get("comments"),
        "created_by": first.get("createdByUserName"),
        "lines": [
            {
                "glId": x["glAccountId"],
                "glCode": x["glAccountCode"],
                "name": x["glAccountName"],
                "type": x["entryType"]["value"].upper(),
                "amount": x["amount"],
            }
            for x in lines
        ],
        "entry_ids": [x["id"] for x in lines if "id" in x],
    }


def day(value) -> str | None:
    """Fineract's [2026, 10, 5], as 2026-10-05."""
    return date(*value).isoformat() if value else None


# What a run keeps of its entry: what its emails show
POSTED = ("transaction_id", "transaction_date", "created_on", "office", "currency", "lines")


def read_back(mifos_transaction_id: str, debit: list, credit: list, code=None) -> dict:
    """What Mifos has for the transaction, and what differs from what we posted, if anything."""
    wanted = [line(d, "DEBIT") for d in debit] + [line(c, "CREDIT") for c in credit]
    if code or mifos_transaction_id.startswith(STUB):
        # The stub echoes what we posted, with no dates or office's name. "mismatch" drops a line
        simulate("mifos_read", code)
        found = {
            "transaction_id": mifos_transaction_id,
            "transaction_date": None,
            "created_on": None,
            "office": {"id": int(os.environ.get("MIFOS_OFFICE_ID", "1")), "name": None},
            "currency": os.environ.get("MIFOS_CURRENCY", "USD"),
            "lines": wanted[:-1] if code == "mismatch" else wanted,
            "entry_ids": [],
        }
    else:
        found = read(mifos_transaction_id)
    log("mifos read back", mifos_transaction_id=mifos_transaction_id, lines=len(found["lines"]))
    return {
        "mifos_transaction_id": mifos_transaction_id,
        "entry": found,
        "posted": {k: found[k] for k in POSTED},
        "mismatch": mismatch(wanted, found["lines"]),
    }


def line(d: dict, side: str) -> dict:
    return {"glId": d["glId"], "glCode": d["glCode"], "name": d["name"], "type": side, "amount": d["amount"]}


def mismatch(wanted: list, got: list) -> str | None:
    """Each line we posted is there once, account, side and amount, and nothing else is."""

    def key(x: dict) -> tuple:
        return x["glId"], x["type"], round(float(x["amount"]), 2)

    missing, extra = [key(x) for x in wanted], []
    for x in got:
        if key(x) in missing:
            missing.remove(key(x))
        else:
            extra.append(key(x))

    def say(keys: list) -> str:
        return ", ".join(f"{side.lower()} {amount:,.2f} to GL {gl}" for gl, side, amount in keys)

    parts = ([f"missing {say(missing)}"] if missing else []) + ([f"not ours {say(extra)}"] if extra else [])
    return "; ".join(parts) or None
