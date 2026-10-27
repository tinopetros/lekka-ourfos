"""What every form's submission has, whichever form it is. The trigger builds it, and everything after it reads it.

Copied into the trigger's zip by `make package`, with requisition.py and forms.py, so it only imports pydantic.
"""

import re
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

# The form's response_id names the submission's document (docs/phase10/adr.md 3), so only what Firestore takes as an id
ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_number: int
    response_id: str = Field(pattern=ID.pattern)
    form_id: str | None = None
    form_name: str | None = None
    submitted_by: str
    submitted_at: AwareDatetime

    def to_json(self) -> dict:
        """For the workflow and the model: ISO 8601 dates, and nothing that's absent."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_firestore(self) -> dict:
        """submitted_at as a Timestamp."""
        return self.model_dump(exclude_none=True)


# What an answer is, for the forms we draw: the type checks it, `kind` tells the UI how to ask. USD only, so an
# amount is a number to the cent
Amount = Annotated[float, Field(ge=0, multiple_of=0.01, json_schema_extra={"kind": "amount"})]
LongText = Annotated[str, Field(json_schema_extra={"kind": "long"})]
# Drive ids, or gs:// refs into our attachments bucket
FileRefs = Annotated[list[str], Field(json_schema_extra={"kind": "files"})]
Months = Annotated[int, Field(ge=1)]
DriveFolder = Annotated[str, Field(pattern=r"^https://drive\.google\.com/drive/(u/\d+/)?folders/[A-Za-z0-9_-]+")]
