from fastapi import APIRouter, Query, Request

from common import log, simulate

router = APIRouter(prefix="/mifos/journal-entries")


@router.post("")
def post(request: Request, body: dict):
    # Logged before simulating, so a "timeout" looks like a post that landed but answered late.
    # Counting these lines per execution is how we prove a timeout never posts twice
    log(request, "mifos post", reference=body["reference"], debit=body["debit"], credit=body["credit"])
    simulate(request, "mifos_post", body.get("simulate"))
    return {"transaction_id": f"stub-txn-{body['reference']}"}


@router.get("/{transaction_id}")
def read_back(request: Request, transaction_id: str, code: str | None = Query(None, alias="simulate")):
    simulate(request, "mifos_read", code)
    log(request, "mifos read back", transaction_id=transaction_id)
    lines = [{"glCode": "6100", "type": "DEBIT"}, {"glCode": "1100", "type": "CREDIT"}]
    if code == "mismatch":
        lines = lines[:1]
    return {"transaction_id": transaction_id, "lines": lines}
