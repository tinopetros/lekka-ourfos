"""The mifos sync: Mifos's clients, loans and manual journal entries, kept in the mifos bucket each night.

Clients and loans, under <kind>/: dt=<date>/part-0001.jsonl, the first snapshot, written once; latest/part-0001.jsonl, replaced
each night; _changes.jsonl, a line for each one new, changed or gone since the night before; _perf.jsonl, each night's
timings and counts, failures too. Each record as Mifos lists it, plus _fetched_at.

Manual journal entries, under manual_journal_entries/: from=<first day>/lines.jsonl, a calendar month a file, Mifos's
lines as it lists them. Entries don't change once booked, so a night rewrites only this month's file, and in a month's
first week last month's too, for entries booked late with past dates. Older months are left as they are.

Mifos is easily overwhelmed, so a night reads it gently: a page at a time, a pause between, never retried. A failure
writes nothing but its line in _perf.jsonl, and the next night compares against the last good list, so it catches up.
"""

import json
import re
import time
from datetime import UTC, date, datetime, timedelta, timezone

from fastapi import HTTPException
from mifos_connector import MifosError

from common import log
from integrations import mifos, mifos_bucket

LISTS = {"clients", "loans"}
JOURNAL = "manual_journal_entries"
KINDS = LISTS | {JOURNAL}
PAGE = 200
JOURNAL_PAGE = 500
# Mifos books in Harare's time, which has no daylight saving
HARARE = timezone(timedelta(hours=2))
# How many days into a month last month is read again, for entries booked late with past dates
LATE = 7
# Between pages, so Mifos is never asked twice at once. Loans' 7 pages and pauses fit well within Cloud Run's 300s
PAUSE = 15
# A page slower than this means Mifos is struggling: stop rather than add to it
SLOW = 60
# What the calendar moves on its own, every active loan every night: kept in latest/, never a change
CALENDAR = re.compile(r"overdue|arrears|npa|delinquen", re.IGNORECASE)
PART = "part-0001.jsonl"


def run(kind: str) -> dict:
    if kind not in KINDS:
        raise HTTPException(404, f"no mifos sync for {kind}")
    if not mifos_bucket.bucket():
        # Dev's Mifos tenant copies prod's and is overloaded already: nothing is mirrored from it
        raise HTTPException(409, "the mifos sync runs on prod only: no mifos bucket here")
    at = datetime.now(UTC).isoformat(timespec="seconds")
    started = time.monotonic()
    if kind == JOURNAL:
        return run_journal(at, started)
    try:
        rows, pages = fetch(kind)
    except (MifosError, SlowMifos) as e:
        perf(kind, {"at": at, "kind": kind, "error": str(e)[:300], "seconds": round(time.monotonic() - started, 2)})
        log(f"mifos sync failed: {kind}", "ERROR", kind=kind, error=str(e))
        raise HTTPException(503, f"mifos sync of {kind} stopped: {e}") from e

    fetched = {x["id"]: x | {"_fetched_at": at} for x in rows}
    text = "".join(json.dumps(x) + "\n" for x in fetched.values())
    previous = mifos_bucket.read(f"{kind}/latest/{PART}")
    firsts = [n for n in mifos_bucket.names(f"{kind}/dt=") if n.endswith(PART)]
    if previous is None and firsts:
        previous = mifos_bucket.read(firsts[0])
    if not firsts:
        mifos_bucket.write(f"{kind}/dt={at[:10]}/{PART}", text)
    changes = compare(as_ids(previous), fetched, at) if previous is not None else []
    if changes:
        mifos_bucket.append(f"{kind}/_changes.jsonl", "".join(json.dumps(c) + "\n" for c in changes))
    mifos_bucket.write(f"{kind}/latest/{PART}", text)

    counts = {c: sum(1 for x in changes if x["change"] == c) for c in ("new", "changed", "gone")}
    record = {
        "at": at,
        "kind": kind,
        "rows": len(rows),
        "pages": pages,
        "read_seconds": round(sum(pages), 2),
        "seconds": round(time.monotonic() - started, 2),
        "bytes": len(text),
        "first": previous is None,
    } | counts
    perf(kind, record)
    log(f"mifos sync done: {kind}", **record)
    return record


class SlowMifos(Exception):
    pass


def months(today: date) -> list[tuple[date, date]]:
    """This month, and last month too in a month's first week."""
    first = today.replace(day=1)
    ranges = [(first, month_end(first))]
    if today.day <= LATE:
        last = (first - timedelta(days=1)).replace(day=1)
        ranges.insert(0, (last, month_end(last)))
    return ranges


def month_end(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def run_journal(at: str, started: float) -> dict:
    today = datetime.now(HARARE).date()
    records = []
    for n, (frm, to) in enumerate(months(today)):
        if n:
            time.sleep(PAUSE)
        try:
            lines, pages = fetch_journal(frm, to)
        except (MifosError, SlowMifos) as e:
            failed = {"at": at, "kind": JOURNAL, "from": frm.isoformat(), "to": to.isoformat(), "error": str(e)[:300]}
            perf(JOURNAL, failed | {"seconds": round(time.monotonic() - started, 2)})
            log(f"mifos sync failed: {JOURNAL}", "ERROR", **failed)
            raise HTTPException(503, f"mifos sync of {JOURNAL} stopped at {frm}: {e}") from e
        name = f"{JOURNAL}/from={frm.isoformat()}/lines.jsonl"
        before = {x["transactionId"] for x in as_rows(mifos_bucket.read(name))}
        after = {x["transactionId"] for x in lines}
        mifos_bucket.write(name, "".join(json.dumps(x | {"_fetched_at": at}) + "\n" for x in lines))
        record = {
            "at": at,
            "kind": JOURNAL,
            "from": frm.isoformat(),
            "to": to.isoformat(),
            "pages": pages,
            "seconds": round(sum(pages), 2),
            "lines": len(lines),
            "transactions": len(after),
            "new": len(after - before),
            "gone": len(before - after),
            "people": sorted({x.get("createdByUserName") or "?" for x in lines}),
            "complete": to < today,
        }
        perf(JOURNAL, record)
        records.append(record)
    log(f"mifos sync done: {JOURNAL}", ranges=records)
    return {"at": at, "kind": JOURNAL, "ranges": records, "seconds": round(time.monotonic() - started, 2)}


def fetch_journal(frm: date, to: date) -> tuple[list, list]:
    """A range's manual entries, its lines that is, a page at a time until a page comes back short."""
    lines, pages = [], []
    with mifos.connection(timeout=SLOW + 5) as client:
        while True:
            if pages:
                time.sleep(PAUSE)
            started = time.monotonic()
            items = client.journal_entries.list(
                {
                    "manualEntriesOnly": True,
                    "fromDate": frm.isoformat(),
                    "toDate": to.isoformat(),
                    "dateFormat": "yyyy-MM-dd",
                    "locale": "en",
                    "orderBy": "id",
                    "sortOrder": "ASC",
                    "offset": len(lines),
                    "limit": JOURNAL_PAGE,
                }
            )["pageItems"]
            pages.append(round(time.monotonic() - started, 2))
            lines += items
            if pages[-1] > SLOW:
                raise SlowMifos(f"a page took {pages[-1]}s")
            if len(items) < JOURNAL_PAGE:
                return lines, pages


def fetch(kind: str) -> tuple[list, list]:
    """Every row, by id, a page at a time until a page comes back short: Mifos's own total can't be trusted."""
    rows, pages = [], []
    with mifos.connection(timeout=SLOW + 5) as client:
        listing = getattr(client, kind)
        while True:
            if pages:
                time.sleep(PAUSE)
            started = time.monotonic()
            items = listing.list({"orderBy": "id", "sortOrder": "ASC", "offset": len(rows), "limit": PAGE})["pageItems"]
            pages.append(round(time.monotonic() - started, 2))
            rows += items
            if pages[-1] > SLOW:
                raise SlowMifos(f"a page took {pages[-1]}s")
            if len(items) < PAGE:
                return rows, pages


def as_rows(text: str | None) -> list:
    return [json.loads(x) for x in (text or "").splitlines() if x]


def as_ids(text: str) -> dict:
    return {x["id"]: x for x in as_rows(text)}


def flat(x: dict, prefix: str = "") -> dict:
    """Every field someone moves, nested ones by their path, e.g. status.value"""
    out = {}
    for k, v in x.items():
        if k.startswith("_") or CALENDAR.search(k):
            continue
        if isinstance(v, dict):
            out |= flat(v, f"{prefix}{k}.")
        else:
            out[f"{prefix}{k}"] = v
    return out


def compare(before: dict, after: dict, at: str) -> list:
    """New, gone, or changed with each field's old and new value. One gone keeps its last whole record."""
    changes = [{"id": i, "at": at, "change": "new"} for i in after.keys() - before.keys()]
    changes += [{"id": i, "at": at, "change": "gone", "last": before[i]} for i in before.keys() - after.keys()]
    for i in after.keys() & before.keys():
        old, new = flat(before[i]), flat(after[i])
        fields = {k: [old.get(k), new.get(k)] for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        if fields:
            changes.append({"id": i, "at": at, "change": "changed", "fields": fields})
    return sorted(changes, key=lambda c: c["id"])


def perf(kind: str, record: dict):
    mifos_bucket.append(f"{kind}/_perf.jsonl", json.dumps(record) + "\n")
