"""Our record of manual journal entries, one per Mifos transaction: Lekkai's, and people's in Mifos
(docs/phase12/tdd.md, steps 2 and 3).

Ours are written in the step that posts them, so the record is never behind what we did: what we sent, and the
transaction id Mifos answered with. Mifos isn't read back, since its reads take minutes (docs/phase12/adr.md 11).
People's would come in through the sync (sync.py), paused for now.
"""

import os
from datetime import date, datetime, timedelta, timezone

import store
from common import log
from integrations.mifos import line

COLLECTION = "journal_entries"
# The day we posted it, ours: UTC+2, with no daylight saving
HARARE = timezone(timedelta(hours=2))


def entry(transaction_id: str) -> store.Doc:
    return store.Doc(store.client().collection(COLLECTION).document(transaction_id))


def lines(debit: list, credit: list) -> list[dict]:
    """A post's two sides as one entry's lines, Mifos's way: account, side and amount."""
    return [line(d, "DEBIT") for d in debit] + [line(c, "CREDIT") for c in credit]


def sides(entry_lines: list[dict]) -> tuple[list, list]:
    """An entry's lines back into debits and credits, as a post takes them."""
    return [x for x in entry_lines if x["type"] == "DEBIT"], [x for x in entry_lines if x["type"] == "CREDIT"]


def sent(transaction_id: str, debit: list, credit: list, on: date) -> dict:
    """What we posted, as a run keeps it and its emails show: Mifos's transaction id, and the rest ours."""
    return {
        "transaction_id": transaction_id,
        "transaction_date": on.isoformat(),
        "created_on": datetime.now(HARARE).date().isoformat(),
        "office": {"id": int(os.environ.get("MIFOS_OFFICE_ID", "1")), "name": None},
        "currency": os.environ.get("MIFOS_CURRENCY", "USD"),
        "lines": lines(debit, credit),
    }


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
    by: str = "lekkai",
    tenant: str | None = None,
):
    """We posted it: the entry, and on the submission, its list and which entry is live. by is lekkai, or the person
    who asked for a correction. tenant is the Mifos tenant it's in, so what undoes it posts there too.

    After the side effect, so a failure is logged and never raised: what happened already happened."""
    try:
        entry(transaction_id).save(
            **sent(transaction_id, debit, credit, on),
            reference_number=reference,
            comments=comments,
            source="ourfos",
            by=by,
            form=form,
            submission=submission,
            run=run,
            status="live",
            **({"reverses": reverses} if reverses else {}),
            **({"tenant": tenant} if tenant else {}),
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
