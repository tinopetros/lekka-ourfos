"""The form's webhook payload, every value a string, into a clean Requisition. Nothing is guessed."""

import re
from datetime import UTC, date, datetime

from pydantic import ValidationError

from requisition import Files, Requisition

FILE_FIELDS = tuple(Files.model_fields)

# Month names only: 04/05/2026 reads two ways, so slashes aren't accepted until a real payload pins them
DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y")

# Drive's open?id=, file/d/ and uc?id= links, inside anchors or not, whatever separates them. Or a gs:// ref,
# kept whole: the service decides whether it may read that bucket
FILE_REF = re.compile(
    r"drive\.google\.com/(?:open\?id=|file/d/|uc\?(?:export=\w+&)?id=)([A-Za-z0-9_-]+)|(gs://[a-z0-9._-]+/[^\s\"'<>,]+)"
)
CURRENCY = re.compile(r"^(US\$|USD|ZWL|ZIG|\$)", re.IGNORECASE)
# Commas only as thousands separators, so 1.200,00 is refused rather than read as 1.2
AMOUNT = re.compile(r"^(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")


class Invalid(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def clean(raw: dict) -> Requisition:
    errors = []
    fields = {}

    def text(key: str) -> str | None:
        value = raw.get(key)
        if value is None:
            return None
        if not isinstance(value, str | int | float):
            errors.append(f"{key}: not text")
            return None
        return str(value).strip() or None

    def parse(key: str, to, into: str):
        value = text(key)
        if value is None:
            return
        try:
            fields[into] = to(value)
        except ValueError as e:
            errors.append(f"{key}: {e}")

    for key, (into, to) in FIELDS.items():
        parse(key, to, into)
    fields["files"] = {key: file_refs(text(key) or "") for key in FILE_FIELDS}

    if errors:
        raise Invalid(errors)
    try:
        return Requisition(**fields)
    except ValidationError as e:
        # Named as the form names them, since that's who reads the 400
        form_key = {into: key for key, (into, _) in FIELDS.items()}
        raise Invalid(
            [f"{form_key.get(err['loc'][0], err['loc'][0])}: {err['msg'].lower()}" for err in e.errors()]
        ) from e


def response_number(value: str) -> int:
    # Negative only from fixtures: no real form has one, so a test run never shares a subject with a real requisition
    if not value.removeprefix("-").isdigit():
        raise ValueError("not a whole number")
    return int(value)


def email(value: str) -> str:
    if "@" not in value or " " in value:
        raise ValueError("not an email address")
    return value.lower()


def amount(value: str) -> float:
    value = CURRENCY.sub("", re.sub(r"\s", "", value))
    if not AMOUNT.match(value):
        raise ValueError("not a number")
    return float(value.replace(",", ""))


def day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()  # noqa: DTZ007  a date, no zone to have
        except ValueError:
            pass
    raise ValueError(f"not a date we can read without guessing: {value!r}")


def epoch_ms(value: str) -> datetime:
    """Milliseconds since 1970, in UTC. The form's response_date has no zone, so its time depends on the form's settings"""
    if not (value.isdigit() and len(value) == 13):
        raise ValueError(f"not epoch milliseconds: {value!r}")
    return datetime.fromtimestamp(int(value) / 1000, UTC)


def file_refs(value: str) -> list[str]:
    """Drive ids and gs:// refs, in the order given, each once."""
    return list(dict.fromkeys(drive or gcs for drive, gcs in FILE_REF.findall(value)))


# The form's key: the clean field, and how to read it
FIELDS = {
    "response_number": ("response_number", response_number),
    "response_id": ("response_id", str),
    "form_id": ("form_id", str),
    "form_name": ("form_name", str),
    "submitter_email_address": ("submitted_by", email),
    "created_at": ("submitted_at", epoch_ms),
    "payable_to": ("payable_to", str),
    "total_amount": ("amount", amount),
    "date_disbursed": ("disbursed_on", day),
    "comment": ("comment", str),
}
