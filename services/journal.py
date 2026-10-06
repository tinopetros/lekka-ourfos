"""Our record of manual journal entries, one per Mifos transaction: Lekkai's, and people's in Mifos
(docs/phase12/tdd.md, steps 2 and 3).

Lekkai's are written in the step that posts them, so the record is never behind what we did. The read-back adds what
only Mifos knows. People's come in through the sync (sync.py).
"""

import os
from datetime import date

import store
from common import log
from integrations.mifos import line

COLLECTION = "journal_entries"


def entry(transaction_id: str) -> store.Doc:
    return store.Doc(store.client().collection(COLLECTION).document(transaction_id))


def lines(debit: list, credit: list) -> list[dict]:
    """A post's two sides as one entry's lines, Mifos's way: account, side and amount."""
    return [line(d, "DEBIT") for d in debit] + [line(c, "CREDIT") for c in credit]


def sides(entry_lines: list[dict]) -> tuple[list, list]:
    """An entry's lines back into debits and credits, as a post takes them."""
    return [x for x in entry_lines if x["type"] == "DEBIT"], [x for x in entry_lines if x["type"] == "CREDIT"]


def posted(
    form: str,
    submission: str,
    run: str,
    transaction_id: str,
    debit: list,
    credit: list,
    on: date,
    reference: str,
    comments: str,
    reverses: str | None = None,
):
    """Lekkai posted it: the entry, and on the submission, its list and which entry is live.

    After the side effect, so a failure is logged and never raised: what happened already happened."""
    try:
        entry(transaction_id).save(
            transaction_id=transaction_id,
            transaction_date=on.isoformat(),
            reference_number=reference,
            comments=comments,
            office={"id": int(os.environ.get("MIFOS_OFFICE_ID", "1")), "name": None},
            currency=os.environ.get("MIFOS_CURRENCY", "USD"),
            lines=lines(debit, credit),
            source="lekkai",
            form=form,
            submission=submission,
            run=run,
            status="live",
            **({"reverses": reverses} if reverses else {}),
            recorded_at=store.NOW,
        )
        if reverses:
            entry(reverses).save(status="reversed", reversed_by=transaction_id)
        parent = store.submission(form, submission)
        listed = parent.get().get("journal_entries") or []
        # A reversal leaves nothing live until the corrected lines are posted
        parent.save(
            journal_entries=listed + ([] if transaction_id in listed else [transaction_id]),
            live_entry=None if reverses else transaction_id,
        )
    except Exception as e:  # noqa: BLE001  anything at all: the post already happened
        log(f"not recorded: {e}", "ERROR", journal_entry=transaction_id)


def read_back(found: dict):
    """What only Mifos knows of an entry we posted: when it was made, by whom, its ids, and its own lines."""
    keep = ("transaction_date", "created_on", "office", "currency", "created_by", "lines", "entry_ids")
    entry(found["transaction_id"]).record(**{k: found[k] for k in keep if found.get(k) is not None})
