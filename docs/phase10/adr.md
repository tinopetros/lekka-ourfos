# Phase 10: decisions and shortcuts

### 1. One submission, one run: receipt is shared code, not a shared run

- A run of its own for receipt, which then starts the form's workflow, would split one submission across two executions: two logs to follow, and a second run that may never start, with nobody left to hand over
- So each form's workflow receives and acknowledges itself, through the same service endpoints
- A later workflow, an approval or a reversal, is a run of its own on the same submission, started by whatever asks for it, not a continuation of receipt
- `intake` serves all three new forms for now. A form gets its own workflow when it gets its own steps

### 2. The workflows share one file of plumbing

- Workflows can't call a subworkflow in another definition, and `call_service`, `handover`, `complete` and the retry predicates are about 200 lines each workflow would copy
- `workflows/lib.workflows.yaml` holds them, and Terraform appends it to each workflow's own file. Both are maps of subworkflows, so the join is still one valid definition
- A change to the plumbing redeploys every workflow, which is what we'd want

### 3. A submission is the document, and each run is one under it

- Closes phase 4 ADR 3: the document id was the execution id, one document per run, which leaves a later run on the same requisition, a reversal, nowhere to go
- Keyed by the form's `response_id`, so a second run of one submission, the add-on firing twice or a re-run, lands on the same document. Our own front end will bring ids of its own, as phase 4 said
- What was submitted, and the thread, are the submission's. What a run did is the run's. The submission mirrors its latest run's status, for lists
- One collection per form: their answers have nothing in common but who sent them, and each will be listed on its own
- No rewrite of old documents: they're keyed by execution id and have no `runs`, so they're easy to find and delete. Prod's are tests
- Not taken: **one `submissions` collection with a `form` field**, as ourfos-v2 did. One place to list everything, but every query filters by form, and each form's indexes share one collection

### 4. Strict only where a step reads the value

- Phase 5 ADR 3 made the requisition's types strict, since classify and post read them. Nothing reads a vehicle log's odometer yet, and refusing one for `52,204 km` loses a log nobody would have checked
- So the new forms clean their identity and subject fields strictly, and keep every other answer as text
- A field gets its type when a step reads it, or when the front end collects it typed

### 5. The trigger still only starts runs

- It could save the submission before starting the run, so a Workflows outage loses nothing: the submission is keyed by `response_id` now, and `receive` would write the same document
- Not now: the trigger would need Firestore and the models, and stops being a thin gate. A failed start is a 5xx, which the alert TODO in the README is for, and the form's response sheet still has it
- **Revisit** if a start ever fails for real

### 6. Write-offs go to `lekkai@` and `directors@`

- Directors decide a write-off, and `lekkai@` keeps every thread
- Leon's write-off emails went to `loan-officers@` too. Every write-off to every loan officer may be too noisy, so not yet
- **Revisit** when the loan officers ask, or when a write-off's workflow needs them to act
