from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

import expenser_runner
from common import log, simulate

router = APIRouter(prefix="/requisitions")


@router.post("/classify")
async def classify(request: Request, body: dict):
    code = body.get("simulate")
    amount = body["requisition"]["amount"]
    if not code:
        classification = await expenser_runner.classify(body["requisition"])
        log(request, "classify", amount=amount, approve=classification["approve"], by="expenser")
        return classification

    # "stub", or a forced failure. In a thread, so a simulated hang can't block the event loop
    await run_in_threadpool(simulate, request, "classify", code)
    log(request, "classify", amount=amount)

    if code == "rejected":
        return {"approve": False, "reason": "No manager signature", "debit": [], "credit": []}
    return {
        "approve": True,
        "reason": "Stub: approved",
        "debit": [{"glCode": "6100", "amount": amount}],
        # "unbalanced" gives check something to catch
        "credit": [{"glCode": "1100", "amount": amount - (1 if code == "unbalanced" else 0)}],
    }
