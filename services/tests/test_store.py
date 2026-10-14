"""A run's status, and what it copies onto its submission, against a transaction in memory."""

import store

save_status = store._save_status.to_wrap


class Ref:
    def __init__(self, docs, path):
        self.docs, self.path, self.id = docs, path, path[-1]

    def get(self, transaction):
        return type("Snapshot", (), {"to_dict": lambda _: self.docs.get(self.path)})()


class Transaction:
    def __init__(self, docs):
        self.docs = docs

    def set(self, ref, fields, merge):
        self.docs.setdefault(ref.path, {}).update(fields)


def test_a_submissions_first_status_says_when_we_received_it_and_a_later_one_never_moves_it():
    docs = {}
    run, submission = Ref(docs, ("s", "run-1")), Ref(docs, ("s",))
    save_status(Transaction(docs), run, submission, {"status": "received"})
    assert docs[("s",)]["received_at"] is store.NOW and docs[("s",)]["status"] == "received"
    docs[("s",)]["received_at"] = "then"
    save_status(Transaction(docs), Ref(docs, ("s", "run-2")), submission, {"status": "handed_over"})
    assert docs[("s",)]["received_at"] == "then" and docs[("s",)]["status"] == "handed_over"


def test_an_invalid_submissions_handover_is_its_first_status():
    docs = {}
    save_status(Transaction(docs), Ref(docs, ("s", "run-1")), Ref(docs, ("s",)), {"status": "handed_over"})
    assert docs[("s",)]["received_at"] is store.NOW


def test_a_refused_correction_touches_nothing_on_the_submission():
    docs = {("s",): {"status": "done", "received_at": "then"}}
    save_status(Transaction(docs), Ref(docs, ("s", "c")), Ref(docs, ("s",)), {"status": "refused"})
    assert docs[("s",)] == {"status": "done", "received_at": "then"}
