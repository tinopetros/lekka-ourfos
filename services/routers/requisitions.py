from fastapi import APIRouter, Request

from common import log, simulate

router = APIRouter(prefix="/requisitions")


@router.post("/classify")
def classify(request: Request, body: dict):
    code = body.get("simulate")
    simulate(request, "classify", code)
    amount = body["requisition"]["amount"]
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
