"""The mifos sync: Mifos's clients and loans, kept in the mifos bucket each night.

Per kind, under <kind>/: dt=<date>/part-0001.jsonl, the first snapshot, written once; latest/part-0001.jsonl, replaced
each night; _changes.jsonl, a line for each one new, changed or gone since the night before; _perf.jsonl, each night's
timings and counts, failures too. Each record as Mifos lists it, plus _fetched_at.

Mifos is easily overwhelmed, so a night reads it gently: a page at a time, a pause between, never retried. A failure
writes nothing but its line in _perf.jsonl, and the next night compares against the last good list, so it catches up.
"""

import json
import re
import time
from datetime import UTC, datetime

from fastapi import HTTPException
from mifos_connector import MifosError

from common import log
from integrations import mifos, mifos_bucket

KINDS = {"clients", "loans"}
PAGE = 200
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


def as_ids(text: str) -> dict:
    return {x["id"]: x for x in map(json.loads, text.splitlines()) if x}


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
