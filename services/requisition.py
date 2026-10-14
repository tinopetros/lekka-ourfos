"""The requisition, clean. The trigger builds it from the form, and everything after it reads it through this."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from submission import Submission


class Files(BaseModel):
    """Per upload field: Drive file ids, or gs:// refs into our attachments bucket. Each titled as its question is on
    the form, which is what the emails and the UI call it."""

    model_config = ConfigDict(extra="forbid")

    signed_requisition_form: list[str] = Field([], title="Signed Requisition Form")
    receipts: list[str] = Field([], title="Receipt(s)")
    invoices: list[str] = Field([], title="Invoice(s)")

    @classmethod
    def label(cls, field: str) -> str:
        return cls.model_fields[field].title or field


class Requisition(Submission):
    # What the requisition's paper says, and Mifos's reference. Until the form asks, Mifos gets the response number
    reference_number: str | None = None
    payable_to: str = Field(min_length=1)
    amount: float = Field(gt=0)
    disbursed_on: date | None = None
    comment: str | None = None
    files: Files = Files()

    def to_firestore(self) -> dict:
        """disbursed_on as YYYY-MM-DD, since Firestore has no date."""
        doc = super().to_firestore()
        if self.disbursed_on:
            doc["disbursed_on"] = self.disbursed_on.isoformat()
        return doc
