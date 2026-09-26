# Phase 4: decisions and shortcuts

### 1. One service per workflow

- The workflow only knows `/requisitions/*`. That service owns the state and calls Mifos, Gmail and expenser for it
- In process for now, but each module keeps a remote-shaped interface (dicts in and out, HTTP statuses out), so a network hop later swaps one module's insides
- **Revisit when** a second workflow needs Mifos or Gmail, or one of them needs its own scaling or identity

### 2. The workflow carries ids, the document carries data

- Steps read the requisition and classification from Firestore rather than from the workflow's body
- Less of the requisition in execution history, which keeps step arguments for 90 days
- It costs a read per step and makes every step depend on Firestore. Both are cheap next to a model call or Mifos
- Handover is the exception: it gets what it needs in the call, so we can still email someone when the database is the problem

### 3. The document id is the execution id

- Fixtures reuse response numbers, so keying on `response_number` would have concurrent runs overwriting each other
- **Revisit** with phase 1 ADR 6: when a re-run should skip `post`, key on `response_number` and hang its executions under it

### 4. A status only where it changes what we'd tell someone

- `received`, `classified`, `posted`, then how it ended. `get_thread`, `notify` and `confirm` don't move it

### 5. A write never undoes a side effect

- Mifos takes the post, then writing `posted` fails. Raising would hand over with "post failed" while the money is in the ledger, and a re-run might post it twice
- So after a post, a failed write is logged, not raised
- A failed write before anything leaves the building fails the step, which is safe to retry
- `complete` is best effort and never turns a finished run red. A red execution may miss its final status; its history has it

### 6. Saved by the workflow's first step, not the trigger

- One writer, the requisition service
- But a requisition that never starts an execution, or fails at `receive`, isn't saved anywhere and nobody is told
- **Revisit** with real intake: save in the trigger first, and tell the sender when it can't start

### 7. Infra grants our project roles, and our deployer none

- Infra makes our accounts, so it now also decides what they may do project-wide. Every project grant is reviewed in one place
- Our deployer loses `projectIamAdmin`, the most powerful thing it held, even conditioned. It keeps who may call our own resources, which `run.admin` covers
- Replaces phase 2 ADR 2 and phase 3 ADR 5
- The cost: a new role for one of our accounts is an infra PR first, and why `ourfos-services` needs it lives in the other repo, as a comment on the grant

### 8. Requisitions are stored, not logged

- Phase 3 ADR 8 holds, and `log_start` stops logging the requisition. The database is IAM only; infra's rules deny every client

### 9. Dev only this phase

- The first phase that keeps data. Nothing is tagged into prod until the document shape has settled
- Dev fills with smoke documents. **Revisit** with a TTL, as infra's notes suggest
