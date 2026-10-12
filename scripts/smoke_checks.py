"""What smoke's runs wrote, read back from dev's Firestore. Standard library and curl
only: the build's image has python3, curl and gcloud, nothing else.

    smoke_checks.py <project> <results dir>

Each run's result is in <results dir>/<form>-<fixture>.json, as `make wait` printed it, and the submission of the try
that passed in <form>-<fixture>.id. Every check runs, then any that failed are listed and it exits 1.
"""

import json
import subprocess
import sys
from pathlib import Path

project, results = sys.argv[1], Path(sys.argv[2])
TOKEN = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
BASE = f"https://firestore.googleapis.com/v1/projects/{project}/databases/ourfos/documents/"
failed = []


def doc(path: str) -> dict | None:
    """A document's fields, or None when there's no such document. Anything else fails the check."""
    out = subprocess.run(
        ["curl", "-s", "-m", "30", "-w", "\n%{http_code}", "-H", f"Authorization: Bearer {TOKEN}", BASE + path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    body, code = out.rsplit("\n", 1)
    if code == "404":
        return None
    if code != "200":
        raise SystemExit(f"firestore {code} for {path}: {body[:300]}")
    return fields(json.loads(body).get("fields", {}))


def fields(typed: dict) -> dict:
    return {k: value(v) for k, v in typed.items()}


def value(v: dict):
    kind, inner = next(iter(v.items()))
    if kind == "integerValue":
        return int(inner)
    if kind == "mapValue":
        return fields(inner.get("fields", {}))
    if kind == "arrayValue":
        return [value(x) for x in inner.get("values", [])]
    return None if kind == "nullValue" else inner


def result(name: str) -> dict:
    return json.loads((results / f"{name}.json").read_text().split("\t")[1])


def check(what: str, ok: bool, seen=None):
    print(f"{'ok  ' if ok else 'FAIL'} {what}" + ("" if ok else f": {seen!r}"))
    if not ok:
        failed.append(what)


def submitted(fixture: str) -> str:
    """The requisition fixture's submission, the try that passed."""
    return (results / f"requisition-{fixture}.id").read_text().strip()


def submission(fixture: str) -> dict:
    return doc(f"requisitions/{submitted(fixture)}") or {}


def entry(transaction: str | None) -> dict:
    return (doc(f"journal_entries/{transaction}") or {}) if transaction else {}


def expense_run(fixture: str) -> dict:
    """The run the form started, whichever ran since: a correction is a run on the submission too."""
    out = subprocess.run(
        [
            "curl",
            "-s",
            "-m",
            "30",
            "-H",
            f"Authorization: Bearer {TOKEN}",
            f"{BASE}requisitions/{submitted(fixture)}/runs",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    runs = [fields(d.get("fields", {})) for d in json.loads(out).get("documents", [])]
    return next((r for r in runs if r.get("workflow") == "expense"), {})


# happy: posted, its entry ours and live, and the run keeps Mifos's dates. The correction has since moved it on
happy = result("requisition-happy")["mifos_transaction_id"]
posted = entry(happy)
check(
    "happy's entry is ours, by Lekkai, with its run",
    posted.get("source") == "ourfos" and posted.get("by") == "lekkai" and bool(posted.get("run")),
    posted,
)

check("happy's comments start Subject:", (posted.get("comments") or "").startswith("Subject: "), posted.get("comments"))
check("happy's entry has Mifos's dates", bool(posted.get("transaction_date") and posted.get("created_on")), posted)
check("happy's entry has Mifos's ids", len(posted.get("entry_ids") or []) >= 2, posted.get("entry_ids"))
first = doc(f"requisitions/{submitted('happy')}/runs/{posted.get('run')}") or {}
dates = first.get("posted") or {}
check(
    "happy's run keeps transaction_date and created_on",
    bool(dates.get("transaction_date") and dates.get("created_on")),
    dates,
)

# correct, on happy: reversed, linked both ways, and the new entry live
corrected = result("correction-correct")
reversal, new = corrected["reversal"], corrected["mifos_transaction_id"]
s = submission("happy")
check("happy's live entry is the correction's", s.get("live_entry") == new, s.get("live_entry"))
check(
    "happy reads posted, reversed, posted", s.get("journal_entries") == [happy, reversal, new], s.get("journal_entries")
)
check(
    "happy's original is reversed by the mirror",
    {"status": "reversed", "reversed_by": reversal}.items() <= entry(happy).items(),
    entry(happy),
)
check("the mirror reverses the original", entry(reversal).get("reverses") == happy, entry(reversal))
check(
    "the correction's entries are by who asked",
    entry(reversal).get("by") == entry(new).get("by") == "lekkai@lekkacredit.com",
    entry(new),
)
mirror = {(x["type"], x["glId"]) for x in entry(reversal).get("lines") or []}
original = {("CREDIT" if x["type"] == "DEBIT" else "DEBIT", x["glId"]) for x in posted.get("lines") or []}
check("the mirror swaps every line", bool(mirror) and mirror == original, (mirror, original))
check(
    "the mirror is on the original's date",
    entry(reversal).get("transaction_date") == posted.get("transaction_date"),
    entry(reversal),
)
check("the new entry is live", entry(new).get("status") == "live", entry(new))

# reverse-only, on happy-gcs: nothing live after
s = submission("happy-gcs")
check("happy-gcs has nothing live", "live_entry" in s and s["live_entry"] is None, s.get("live_entry"))

# mifos-off: no entry, and no third email
s = submission("mifos-off")
check("mifos-off has no journal entries", not s.get("journal_entries") and not s.get("live_entry"), s)
check("mifos-off is done, its refused correction aside", s.get("status") == "done", s.get("status"))
emails = expense_run("mifos-off").get("emails") or {}
check("mifos-off sent no third email", "suggestion" in emails and "confirmation" not in emails, sorted(emails))

# the sync: its mark is what it said
synced = json.loads((results / "sync.json").read_text().split("\t")[1])
mark = doc("syncs/journal_entries")
if synced.get("skipped"):
    check("no mark, none written", mark is None, mark)
else:
    check("the mark is the sync's", ((mark or {}).get("last_entry_id") or 0) >= synced["last_entry_id"], mark)

if failed:
    sys.exit(f"{len(failed)} failed")
