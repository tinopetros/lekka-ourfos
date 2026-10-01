"""What every form's submission has, whichever form it is. The trigger builds it, and everything after it reads it.

Copied into the trigger's zip by `make package`, with requisition.py and forms.py, so it only imports pydantic.
"""

import re

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
