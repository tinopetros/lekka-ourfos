"""received_at on every submission from before it was written: the earliest of its runs'
starts, or failing those, when it was submitted or last changed. Never overwrites one that's there.

    cd services && PYTHONPATH=. uv run python ../scripts/backfill_received_at.py ourfos-dev           # what it would write
    cd services && PYTHONPATH=. uv run python ../scripts/backfill_received_at.py ourfos-dev --write   # writes it
"""

import sys

from google.cloud import firestore

from forms import FORMS


def received(doc: firestore.DocumentSnapshot):
    starts = [
        r.to_dict().get("execution", {}).get("started_at")
        for r in doc.reference.collection("runs").stream()
        if isinstance(r.to_dict().get("execution"), dict)
    ]
    data = doc.to_dict()
    return min([s for s in starts if s] or [None]) or data.get("submitted_at") or data.get("updated_at")


def main(project: str, write: bool):
    db = firestore.Client(project=project, database="ourfos")
    for form, spec in FORMS.items():
        done = missing = 0
        for doc in db.collection(spec.collection).stream():
            if doc.to_dict().get("received_at"):
                continue
            when = received(doc)
            if not when:
                missing += 1
                print(f"{form}/{doc.id}: no time to go by")
                continue
            if write:
                doc.reference.update({"received_at": when})
            done += 1
        print(f"{form}: {done} {'written' if write else 'to write'}, {missing} without a time")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], "--write" in sys.argv[2:])
