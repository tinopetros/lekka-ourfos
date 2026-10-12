"""Mifos's manual journal entries into our record (docs/phase12/tdd.md, step 6). It only adds: entries are taken as
immutable, so ours is never reconciled with Mifos's (docs/phase12/adr.md 6).

Each night, newest entry id first, back to a mark. With a date to start from, the preload: everything since then.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from google.cloud import firestore

import journal
import store
from common import log
from forms import FORMS
from integrations import mifos

KIND = "journal_entries"
PAGE = 200
# Buffer just in case
MARGIN = 10


def mark() -> store.Doc:
    return store.Doc(store.client().collection("syncs").document(KIND))


def journal_entries(since: str | None = None) -> dict:
    if since:
        return preload(date.fromisoformat(since))
    try:
        last = mark().get()["last_entry_id"]
    except HTTPException as e:
        if e.status_code != 404:
            raise
        # No mark: never a read of everything. The preload is by hand.
        log(f"{KIND} not preloaded", "WARNING")
        return {"skipped": "not preloaded"}
    lines, highest, offset = {}, last, 0
    while True:
        page = mifos.manual_entries({"orderBy": "id", "sortOrder": "DESC", "offset": offset, "limit": PAGE})
        fresh = [x for x in page if x["id"] > last - MARGIN]
        for x in fresh:
            highest = max(highest, x["id"])
            if x.get("createdByUserName") != mifos.ours():
                lines.setdefault(x["transactionId"], []).append(x)
        if len(fresh) < len(page) or len(page) < PAGE:
            break
        offset += PAGE
    # Read whole, by id: a page can end halfway through a transaction
    found = {txn: mifos.read(txn) for txn in lines.keys() - held(lines)}
    added = write(found, {})
    raise_mark(highest, added)
    log(f"{KIND} synced", added=added, last_entry_id=highest, was=last)
    return {"added": added, "last_entry_id": highest, "was": last}


def preload(since: date) -> dict:
    """Every manual entry booked since then, ours too: one a run posted is Lekkai's, and names its run."""
    lines, offset = {}, 0
    # A year ahead: an entry can be booked in the future
    until = (datetime.now(UTC) + timedelta(days=366)).date()
    while True:
        page = mifos.manual_entries(
            {
                "fromDate": since.isoformat(),
                "toDate": until.isoformat(),
                "dateFormat": "yyyy-MM-dd",
                "locale": "en",
                "orderBy": "id",
                "sortOrder": "ASC",
                "offset": offset,
                "limit": PAGE,
            }
        )
        for x in page:
            lines.setdefault(x["transactionId"], []).append(x)
        if len(page) < PAGE:
            break
        offset += PAGE
    highest = max((x["id"] for group in lines.values() for x in group), default=0)
    known = held(lines)
    found = {txn: mifos.entry(txn, group) for txn, group in lines.items() if txn not in known}
    added = write(found, posted_by_runs())
    raise_mark(highest, added)
    log(f"{KIND} preloaded", since=since, transactions=len(lines), added=added, last_entry_id=highest)
    return {"added": added, "transactions": len(lines), "last_entry_id": highest}


def held(transactions) -> set[str]:
    """Which of these we already hold, in one read."""
    refs = [journal.entry(txn).ref for txn in transactions]
    return {doc.id for doc in store.client().get_all(refs) if doc.exists} if refs else set()


def posted_by_runs() -> dict:
    """Every transaction a run posted, its mirror too, and which run: {transaction: (form, submission, run)}."""
    forms = {spec.collection: name for name, spec in FORMS.items()}
    found = {}
    for run in store.client().collection_group("runs").stream():
        doc = run.to_dict()
        submission = run.reference.parent.parent
        where = (forms.get(submission.parent.id), submission.id, run.id)
        for txn in (doc.get("mifos_transaction_id"), (doc.get("reversal") or {}).get("transaction_id")):
            if txn:
                found[txn] = where
    return found


def write(found: dict, runs: dict) -> int:
    """New entries, live, in batches. Ours a run posted are Lekkai's, anyone else's Mifos's."""
    batch, n = store.client().batch(), 0
    for txn, entry in found.items():
        batch.set(journal.entry(txn).ref, recorded(txn, entry, runs))
        n += 1
        if n % 400 == 0:
            batch.commit()
            batch = store.client().batch()
    batch.commit()
    return n


def recorded(txn: str, entry: dict, runs: dict) -> dict:
    if txn in runs:
        form, submission, run = runs[txn]
        source = {"source": "ourfos", "by": "lekkai", "form": form, "submission": submission, "run": run}
    elif entry.get("created_by") == mifos.ours():
        source = {"source": "ourfos", "by": "lekkai"}
    else:
        # Who in Mifos is created_by
        source = {"source": "mifos"}
    return entry | source | {"status": "live", "recorded_at": store.NOW}


def raise_mark(highest: int, added: int):
    """Once the sync is done, and only ever up: two at once can't move it back."""
    _raise(store.client().transaction(), mark().ref, highest, added)


@firestore.transactional
def _raise(transaction, ref, highest, added):
    now = (ref.get(transaction=transaction).to_dict() or {}).get("last_entry_id") or 0
    transaction.set(ref, {"last_entry_id": max(now, highest), "last_run_at": store.NOW, "added": added}, merge=True)
