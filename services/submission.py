"""What every form's submission has, whichever form it is. The trigger builds it, and everything after it reads it.

Copied into the trigger's zip by `make package`, with requisition.py and forms.py, so it only imports pydantic.
"""

import functools
import re
from datetime import date
from typing import Annotated, Literal

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
    # Where it came from: our own form, or, when absent, a Google Form's webhook
    source: Literal["ourfos"] | None = None

    def to_json(self) -> dict:
        """For the workflow and the model: ISO 8601 dates, and nothing that's absent."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_firestore(self) -> dict:
        """submitted_at as a Timestamp, and a date as YYYY-MM-DD, since Firestore has no date."""
        doc = self.model_dump(exclude_none=True)
        return {k: v.isoformat() if type(v) is date else v for k, v in doc.items()}


# What an answer is, for the forms we draw: the type checks it, `kind` tells the UI how to ask. USD only, so an
# amount is a number to the cent
Amount = Annotated[float, Field(ge=0, multiple_of=0.01, json_schema_extra={"kind": "amount"})]


@functools.cache
def kinds(model: type[BaseModel]) -> dict[str, str | None]:
    """How each field of a form asks, from its schema: a `kind`, on the field or on what it is when answered."""
    props = model.model_json_schema()["properties"]
    return {
        key: prop.get("kind") or next((a["kind"] for a in prop.get("anyOf", []) if "kind" in a), None)
        for key, prop in props.items()
    }


LongText = Annotated[str, Field(json_schema_extra={"kind": "long"})]
# Drive ids, or gs:// refs into our attachments bucket
FileRefs = Annotated[list[str], Field(json_schema_extra={"kind": "files"})]
Months = Annotated[int, Field(ge=1)]
DriveFolder = Annotated[str, Field(pattern=r"^https://drive\.google\.com/drive/(u/\d+/)?folders/[A-Za-z0-9_-]+")]


# A file uploaded from our own form: its name as picked, after the tag that keeps two of the same name apart
UPLOADED = re.compile(r"/[0-9a-f]{8}-([^/]+)$")


def file_name(ref: str, n: int) -> str:
    """What to call a file: its own name, if it was added from our own form; File 1, File 2 otherwise."""
    uploaded = UPLOADED.search(ref)
    return uploaded.group(1) if uploaded else f"File {n}"
