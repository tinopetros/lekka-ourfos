"""Mifos, stubbed. Dicts in and out, failures as HTTP statuses, so it can move behind a network hop unchanged."""

from common import log, simulate


def post(reference: str, debit: list, credit: list, code=None) -> dict:
    # Logged before simulating, so a "timeout" looks like a post that landed but answered late.
    # Counting these lines per execution is how we prove a timeout never posts twice
    log("mifos post", reference=reference, debit=debit, credit=credit)
    simulate("mifos_post", code)
    return {"mifos_transaction_id": f"stub-txn-{reference}"}


def read_back(mifos_transaction_id: str, debit: list, credit: list, code=None) -> dict:
    """The posted lines, as if Mifos had them. "mismatch" drops one"""
    simulate("mifos_read", code)
    log("mifos read back", mifos_transaction_id=mifos_transaction_id)
    lines = [{"glId": d["glId"], "type": "DEBIT"} for d in debit] + [
        {"glId": c["glId"], "type": "CREDIT"} for c in credit
    ]
    if code == "mismatch":
        lines = lines[:-1]
    return {"mifos_transaction_id": mifos_transaction_id, "lines": lines}
