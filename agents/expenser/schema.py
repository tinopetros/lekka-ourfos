"""What the model writes, and the whole classification code makes of it (docs/phase8/adr.md 2)."""

from pydantic import BaseModel


class Line(BaseModel):
    name: str
    glCode: str
    # What Mifos posts to. glCode is what a person reads
    glId: int
    accountType: str
    amount: float


# The stub answers in this shape too, so the workflow can't tell a model answered
class Classification(BaseModel):
    approve: bool
    reason: str
    debit: list[Line]
    credit: list[Line]
    comments: list[str]


class Said(BaseModel):
    # The account by name only: its code is the chart's. Codes are what the model slipped on, 5035 for 5135 (#24)
    name: str
    amount: float


# The model's output_schema: GL codes, IDs and types are the chart's, filled in after
class Answer(BaseModel):
    approve: bool
    reason: str
    debit: list[Said]
    credit: list[Said]
    comments: list[str]
