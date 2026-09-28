"""The requisition, clean. The trigger builds it from the form, and everything after it reads it through this.

Copied into the trigger's zip by `make package`, so it only imports pydantic.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Files(BaseModel):
    """Drive file ids per upload field. Not fetched yet."""

    model_config = ConfigDict(extra="forbid")

    signed_requisition_form: list[str] = []
    receipts: list[str] = []
    invoices: list[str] = []


class Requisition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_number: int
    response_id: str
    form_id: str | None = None
    form_name: str | None = None
    submitted_by: str
    submitted_at: AwareDatetime
    payable_to: str = Field(min_length=1)
    amount: float = Field(gt=0)
    disbursed_on: date | None = None
    comment: str | None = None
    files: Files = Files()

    def to_json(self) -> dict:
        """For the workflow and the model: ISO 8601 dates, and nothing that's absent."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_firestore(self) -> dict:
        """submitted_at as a Timestamp. disbursed_on as YYYY-MM-DD, since Firestore has no date."""
        doc = self.model_dump(exclude_none=True)
        if self.disbursed_on:
            doc["disbursed_on"] = self.disbursed_on.isoformat()
        return doc
