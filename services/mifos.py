"""Mifos, stubbed. Dicts in and out, failures as HTTP statuses, so it can move behind a network hop unchanged."""

from common import log, simulate


def post(reference: str, debit: list, credit: list, code=None) -> dict:
    # Logged before simulating, so a "timeout" looks like a post that landed but answered late.
    # Counting these lines per execution is how we prove a timeout never posts twice
    log("mifos post", reference=reference, debit=debit, credit=credit)
    simulate("mifos_post", code)
    return {"transaction_id": f"stub-txn-{reference}"}


def read_back(transaction_id: str, code=None) -> dict:
    simulate("mifos_read", code)
    log("mifos read back", transaction_id=transaction_id)
    lines = [{"glCode": "6100", "type": "DEBIT"}, {"glCode": "1100", "type": "CREDIT"}]
    if code == "mismatch":
        lines = lines[:1]
    return {"transaction_id": transaction_id, "lines": lines}
