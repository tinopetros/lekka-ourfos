"""Mifos, through our connector (docs/phase11/tdd.md). Dicts in and out, failures as HTTP statuses.

Dev posts to the demo tenant, prod to default: the books. A test run posts to demo on either, so prod's own smoke
posts for real without touching the books. A fixture's simulate, dev only, keeps phase 5's stub.
"""

import os
import threading
import uuid
from datetime import UTC, date, datetime, timedelta
from functools import cache

import httpx
from fastapi import HTTPException
from mifos_connector import MifosApiError, MifosClient, MifosError, MifosNetworkError, postable

import store
from common import log, simulate

BOOKS = "default"
# Where a test run posts, on dev and prod alike
TEST_TENANT = "demo"
STUB = "stub-txn-"
# How old a tenant's saved accounts may be before Mifos is asked again: they change rarely, and a read is a few seconds
ACCOUNTS_FOR = timedelta(days=1)
# The tenants being read again, so one read is under way at a time per tenant
_refreshing: set[str] = set()
_lock = threading.Lock()
# Under call_service's 20s, so a slow Mifos is ours to call uncertain, not the workflow's
TIMEOUT = 15


def tenant(test: bool = False) -> str:
    """Where a run posts: demo for a test, this environment's tenant otherwise."""
    return TEST_TENANT if test else os.environ["MIFOS_TENANT_ID"]


@cache
def client(tenant: str | None = None) -> MifosClient:
    tenant = tenant or os.environ["MIFOS_TENANT_ID"]
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


def accounts(tenant: str) -> list:
    """The accounts a journal entry can post to in this tenant, by GL code, as last read from Mifos and kept on
    mifos_accounts/{tenant}. Kept ones answer straight away, and are read again behind the answer once a day old, so
    Mifos is asked about daily whatever the restarts: only a tenant never read waits on it"""
    saved = store.client().collection("mifos_accounts").document(tenant).get()
    if not saved.exists:
        return read_accounts(tenant)
    saved = saved.to_dict()
    if datetime.now(UTC) - saved["read_at"] >= ACCOUNTS_FOR:
        with _lock:
            again = tenant not in _refreshing
            _refreshing.add(tenant)
        if again:
            threading.Thread(target=refresh_accounts, args=(tenant,), daemon=True).start()
    return saved["accounts"]


def read_accounts(tenant: str) -> list:
    """Mifos's postable accounts in this tenant, read now and saved"""
    try:
        read = client(tenant).gl_accounts.list({"usage": 1, "disabled": False, "manualEntriesAllowed": True})
    except MifosError as e:
        raise read_failed(e) from e
    found = sorted(
        (
            {"glId": a["id"], "glCode": a["glCode"], "name": a["name"], "type": a["type"]["value"]}
            for a in postable(read)
        ),
        key=lambda a: a["glCode"],
    )
    ref = store.client().collection("mifos_accounts").document(tenant)
    ref.set({"tenant": tenant, "accounts": found, "read_at": datetime.now(UTC)})
    log("mifos accounts read", tenant=tenant, accounts=len(found))
    return found


def refresh_accounts(tenant: str):
    """read_accounts, behind an answer: a failure leaves the saved ones standing, stale rather than none"""
    try:
        read_accounts(tenant)
    except Exception as e:  # noqa: BLE001  anything at all: the saved accounts still answer
        log(f"mifos accounts stale: {e!r}", "WARNING", tenant=tenant)
    finally:
        with _lock:
            _refreshing.discard(tenant)


def connect():
    """One read when an instance starts: Mifos answers, and our user logs in. Logged, never raised (step 3)"""
    tenant = os.environ.get("MIFOS_TENANT_ID")
    try:
        # Our office, not journal entries: Mifos takes minutes to list those, even a day's (docs/phase12/adr.md 11)
        client()._http.get(f"/offices/{int(os.environ.get('MIFOS_OFFICE_ID', '1'))}")
        log("mifos connected", tenant=tenant)
    except (MifosError, HTTPException, KeyError) as e:
        log(f"mifos not connected: {e!r}", "ERROR", tenant=tenant)


def post(
    reference: str, debit: list, credit: list, on: date, comments: str, code=None, tenant: str | None = None
) -> dict:
    # Logged before posting, so a timeout looks like a post that landed but answered late.
    # Counting these lines per execution is how we prove a timeout never posts twice
    log("mifos post", reference=reference, debit=debit, credit=credit, on=on, stub=bool(code), tenant=tenant)
    if code:
        simulate("mifos_post", code)
        # Its own each time: a correction posts twice under one reference
        return {"mifos_transaction_id": f"{STUB}{uuid.uuid4().hex[:13]}"}
    try:
        posted = client(tenant).journal_entries.create(
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


def line(d: dict, side: str) -> dict:
    return {"glId": d["glId"], "glCode": d["glCode"], "name": d["name"], "type": side, "amount": d["amount"]}
