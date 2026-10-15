"""The one-time reshape of old requisitions (scripts/reshape_requisitions.py): what lands where."""

from datetime import UTC, datetime

from scripts.reshape_requisitions import old, plan, run, submission


def at(minute: int) -> datetime:
    return datetime(2026, 9, 30, 12, minute, tzinfo=UTC)


def doc(minute: int, response_id="R1", **more) -> dict:
    return {
        "requisition": {"response_id": response_id, "response_number": 12, "submitted_by": "a@lekkacredit.com"},
        "raw": {"response_id": response_id},
        "response_number": 12,
        "status": "done",
        "execution": {"id": f"e{minute}", "started_at": at(minute), "revision": "r"},
        "updated_at": at(minute + 1),
        **more,
    }


def test_runs_of_one_response_are_one_submission_earliest_first():
    plans = plan({"e2": doc(2), "e1": doc(1), "e3": doc(3, response_id="R2")})
    assert {sid: [e for e, _ in runs] for sid, runs in plans.items()} == {"R1": ["e1", "e2"], "R2": ["e3"]}


def test_a_submission_keeps_the_first_thread_and_the_latest_status():
    first = doc(1, thread={"thread_id": "t1"}, emails={"acknowledgement": {"message_id": "m1"}})
    later = doc(2, status="handed_over", thread={"thread_id": "t2"}, emails={"acknowledgement": {"message_id": "m2"}})
    s = submission(plan({"e1": first, "e2": later})["R1"])
    assert s["thread"] == {"thread_id": "t1"}
    assert s["emails"] == {"acknowledgement": {"message_id": "m1"}}
    assert (s["status"], s["run"]) == ("handed_over", "e2")
    assert s["answers"]["response_id"] == "R1" and s["form"] == "requisition"


def test_a_run_keeps_everything_but_the_submissions():
    r = run(
        doc(
            1,
            classification={"approve": True},
            transaction_id="old-name",
            thread={"thread_id": "t1"},
            emails={"acknowledgement": 1, "suggestion": 2},
        )
    )
    assert r["classification"] == {"approve": True}
    assert r["transaction_id"] == "old-name"
    # Each run started its own thread before phase 10, so keeps it
    assert r["thread"] == {"thread_id": "t1"}
    assert r["emails"] == {"acknowledgement": 1, "suggestion": 2}
    assert r["execution"] == {"started_at": at(1), "revision": "r"}
    assert r["workflow"] == "requisition"
    assert not {"requisition", "raw", "response_number"} & set(r)


def test_a_form_that_couldnt_be_read_keeps_its_runs_own_id():
    plans = plan({"e1": {"raw": {"response_id": "a/b"}, "status": "handed_over"}})
    assert list(plans) == ["e1"]
    assert submission(plans["e1"])["raw"] == {"response_id": "a/b"}


def test_only_old_documents_are_reshaped():
    assert old(doc(1))
    assert not old({"form": "requisition", "answers": {}})
