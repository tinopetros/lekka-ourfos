"""The chart of accounts: what the model is shown, and what code fills in after it (docs/phase8/adr.md 2 and 3).

accounts.csv stays whole, the reference. The model reads four of its columns, and names each line's account by name and
GL code. Its GL ID and type are lookups, never the model's to write.
"""

import csv
import io
from pathlib import Path

ROWS = list(csv.DictReader((Path(__file__).parent / "accounts.csv").read_text().splitlines()))
BY_CODE = {row["GL Code"]: row for row in ROWS}
# Names are unique, as codes are: a line's name is how the model means its account
BY_NAME = {" ".join(row["Account"].lower().split()): row for row in ROWS}

# What the model reads. The rest of the chart is the same on every row, or code's to fill
SHOWN_COLUMNS = ["Account", "GL Code", "Account Type", "Comment"]


def shown() -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, SHOWN_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(ROWS)
    return out.getvalue()
