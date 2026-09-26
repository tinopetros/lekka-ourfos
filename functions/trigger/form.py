"""The form's webhook payload, every value a string, into a clean Requisition. Nothing is guessed."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from requisition import Files, Requisition

HARARE = ZoneInfo("Africa/Harare")
FILE_FIELDS = tuple(Files.model_fields)

# Month names only: 04/05/2026 reads two ways, so slashes aren't accepted until a real payload pins them
DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y")
TIME_FORMATS = ("", ", %I:%M:%S %p", ", %I:%M %p", " %I:%M:%S %p", " %I:%M %p", " %H:%M:%S", " %H:%M")

# open?id=, file/d/ and uc?id= links, inside anchors or not, whatever separates them
DRIVE_ID = re.compile(r"drive\.google\.com/(?:open\?id=|file/d/|uc\?(?:export=\w+&)?id=)([A-Za-z0-9_-]+)")
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
    fields["files"] = {key: drive_ids(text(key) or "") for key in FILE_FIELDS}

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
    if not value.isdigit():
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


def timestamp(value: str) -> datetime:
    """ISO 8601, epoch milliseconds, or a month-name date with an optional time. Harare when no zone is given."""
    if value.isdigit() and len(value) == 13:
        return datetime.fromtimestamp(int(value) / 1000, HARARE)
    parsed = None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        for d in DATE_FORMATS:
            for t in TIME_FORMATS:
                try:
                    parsed = datetime.strptime(value, d + t)  # noqa: DTZ007  Harare, below
                    break
                except ValueError:
                    pass
            if parsed:
                break
    if parsed is None:
        raise ValueError(f"not a time we can read without guessing: {value!r}")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=HARARE)


def drive_ids(value: str) -> list[str]:
    return list(dict.fromkeys(DRIVE_ID.findall(value)))


# The form's key: the clean field, and how to read it
FIELDS = {
    "response_number": ("response_number", response_number),
    "response_id": ("response_id", str),
    "form_id": ("form_id", str),
    "form_name": ("form_name", str),
    "submitter_email_address": ("submitted_by", email),
    "response_date": ("submitted_at", timestamp),
    "payable_to": ("payable_to", str),
    "total_amount": ("amount", amount),
    "date_disbursed": ("disbursed_on", day),
    "comment": ("comment", str),
}
