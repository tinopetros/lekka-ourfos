"""Once: requisitions stored one document per run, keyed by execution id, into phase 10's shape (docs/phase10/adr.md 3).

    requisitions/{execution_id}  ->  requisitions/{response_id}  and  requisitions/{response_id}/runs/{execution_id}

Runs of the same response land under one submission. Its answers, raw and test are the earliest run's, and so are its
thread and first email, since that's the thread everyone has. Its status is the latest run's. Before phase 10 every run
started its own thread, so each run keeps its own thread and first email too. Every field a run had that phase 10
doesn't name, from earlier phases too, is kept on the run as it was: nothing is dropped.

Dry run unless --apply. --source=<database> reads the old documents from another database, such as a backup
imported to check or repair a reshape, and still writes to ourfos. Each submission is one batch: its new documents written and its old ones deleted together, or
not at all. A submission already in the new shape keeps what it has; old runs are only added under it.

    cd services && GOOGLE_CLOUD_PROJECT=ourfos-dev uv run python -m scripts.reshape_requisitions [--apply] [--source=<db>]
"""

import sys
from collections import defaultdict
from datetime import UTC, datetime

from google.cloud import firestore

from submission import ID

# Only the submission's: what was submitted
SUBMISSION = {"requisition", "raw", "test", "response_number"}
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def old(doc: dict) -> bool:
    """Phase 10 documents have a form. Every earlier one doesn't."""
    return "form" not in doc and "answers" not in doc


def submission_id(execution_id: str, doc: dict) -> str:
    """The form's response_id, as phase 10 keys it, or the run's own id when there's no usable one."""
    for source in (doc.get("requisition"), doc.get("raw")):
        rid = (source or {}).get("response_id")
        if isinstance(rid, str) and ID.match(rid):
            return rid
    return execution_id


def started(doc: dict) -> datetime:
    return (doc.get("execution") or {}).get("started_at") or doc.get("updated_at") or EPOCH


def run(doc: dict) -> dict:
    """Everything that was the run's, with phase 10's names where they changed."""
    r = {k: v for k, v in doc.items() if k not in SUBMISSION}
    r["workflow"] = "requisition"  # what it ran as, before expense
    r["test"] = bool(doc.get("test"))
    if execution := doc.get("execution"):
        r["execution"] = {k: v for k, v in execution.items() if k != "id"}
    return r


def plan(docs: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    """Old runs, earliest first, by the submission they belong to."""
    grouped = defaultdict(list)
    for execution_id, doc in docs.items():
        grouped[submission_id(execution_id, doc)].append((execution_id, doc))
    return {sid: sorted(runs, key=lambda r: started(r[1])) for sid, runs in grouped.items()}


def submission(runs: list[tuple[str, dict]]) -> dict:
    first, latest = runs[0][1], runs[-1]
    answers = first.get("requisition")
    s = {
        "form": "requisition",
        "raw": first.get("raw"),
        "test": bool(first.get("test")),
        "status": latest[1].get("status"),
        "run": latest[0],
        "updated_at": max(d.get("updated_at") or EPOCH for _, d in runs),
    }
    if answers:
        s |= {
            "answers": answers,
            "response_number": answers.get("response_number"),
            "submitted_by": answers.get("submitted_by"),
            "submitted_at": answers.get("submitted_at"),
        }
    elif first.get("response_number") is not None:
        s["response_number"] = first["response_number"]
    # The thread everyone has is the first one that was started
    for _, d in runs:
        if d.get("thread"):
            s["thread"] = d["thread"]
            if ack := (d.get("emails") or {}).get("acknowledgement"):
                s["emails"] = {"acknowledgement": ack}
            break
    return {k: v for k, v in s.items() if v is not None}


def main(apply: bool, source: str | None):
    db = firestore.Client(database="ourfos")
    collection = db.collection("requisitions")
    docs = {d.id: d.to_dict() for d in collection.stream()}
    read = firestore.Client(database=source).collection("requisitions").stream() if source else None
    olds = {d.id: d.to_dict() for d in read if old(d.to_dict())} if read else {k: v for k, v in docs.items() if old(v)}
    plans = plan(olds)
    print(
        f"{len(olds)} old documents into {len(plans)} submissions ({sum(not old(v) for v in docs.values())} already new)"
    )
    for sid, runs in sorted(plans.items(), key=lambda p: -len(p[1])):
        s = submission(runs)
        exists = sid in docs and not old(docs[sid])
        print(
            f"  {sid}: {len(runs)} run(s), status {s.get('status')}, thread {'yes' if 'thread' in s else 'no'}"
            + (", submission exists: runs only" if exists else "")
        )
        if not apply:
            continue
        # One batch a submission: Firestore takes up to 500 writes, so a submission with more runs goes in parts,
        # its old documents deleted only in the part that wrote them
        ref = collection.document(sid)
        for i in range(0, len(runs), 200):
            batch = db.batch()
            if i == 0 and not exists:
                batch.set(ref, s)
            for execution_id, doc in runs[i : i + 200]:
                batch.set(ref.collection("runs").document(execution_id), run(doc))
                if execution_id != sid:
                    batch.delete(collection.document(execution_id))
            batch.commit()
    print("applied" if apply else "dry run: nothing written. --apply to write")


if __name__ == "__main__":
    args = sys.argv[1:]
    main("--apply" in args, next((a.split("=", 1)[1] for a in args if a.startswith("--source=")), None))
