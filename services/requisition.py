"""The requisition, clean. The trigger builds it from the form, and everything after it reads it through this."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from submission import Amount, FileRefs, LongText, Submission


# Per upload field: Drive file ids, or gs:// refs into our attachments bucket. Each titled as the form asks it, which
# is what the emails and the UI call it. Comments, not docstrings, here and below: a docstring is the form's own text
class Files(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signed_requisition_form: FileRefs = Field([], title="Signed requisition form")
    receipts: FileRefs = Field([], title="Receipts")
    invoices: FileRefs = Field([], title="Invoices")

    @classmethod
    def label(cls, field: str) -> str:
        return cls.model_fields[field].title or field


# What the form asks, in its order
class RequisitionForm(BaseModel):
    model_config = ConfigDict(extra="forbid", title="Requisition")

    payable_to: str = Field(min_length=1, title="Payable to")
    amount: Amount = Field(gt=0, title="Amount")
    disbursed_on: date | None = Field(None, title="Disbursed on")
    # Mifos's reference too. Until there's one, Mifos gets the response number
    reference_number: str | None = Field(
        None, title="Reference number", description="The number on the paper requisition, if it has one"
    )
    comment: LongText | None = Field(None, title="Comment")
    files: Files = Field(Files(), title="Files")


class Requisition(RequisitionForm, Submission):
    """A requisition as stored: what the form asks, and who sent it when. Nothing of its own."""
