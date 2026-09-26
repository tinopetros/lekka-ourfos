# Phase 5: decisions and shortcuts

### 1. Clean at the edge

- The trigger turns the form's strings into one clean requisition. The workflow, the service, the document and the model only ever see that
- A bad payload is a 400 to whoever sent it, and nothing starts. No `invalid` status, and no document for it
- The form doesn't read the 400. Phase 4 ADR 6's cost again: a bad submission is only in the trigger's logs
- **Revisit** with our own front end: it posts the clean shape, and the trigger learns the source so it can skip cleaning

### 2. `raw` is kept beside the clean requisition, this phase only

- The cleaner is new and the formats aren't pinned yet. When it gets something wrong, `raw` shows what the form actually sent
- It costs a second copy of the requisition in every document
- **Revisit** with our own front end, when there's no form payload to keep

### 3. Strict types, no guessing

- `amount` drops currency signs and thousands commas, and anything left that isn't a positive number is a 400
- A date that reads two ways, like `04/05/2026`, is a 400, not a guess. Money posted on the wrong date is worse than a bounced form
- Only what's required is required. A missing comment or file field is left out

### 4. Files are Drive ids, not fetched

- Pulled out of whatever the form sends, anchors or commas or bare links, as ourfos-v2 did. Stored as lists per field
- Nothing reads them yet. They're ready for when the Workspace service can

### 5. The prompt lifted, minus attachments

- ourfos-v2's prompt and chart of accounts, as they were, except the rules that need a file to judge
- Those rules are swapped for one line: attachments aren't shown, so never reject over one. Otherwise the prompt rejects everything
- So a requisition without a signed form is approved on the form alone. That's the known gap until attachments are back
- Not tuned. The evals phase does that, with this as the baseline
- ourfos-v2 ran it on Claude, and we run Flash-Lite. The same words on another model is an unmeasured change, left for evals too

### 6. Our output schema, not the prompt's format

- The prompt asked for single-line JSON with tuples. That's parsing by hand, and a tuple's order is easy to get wrong
- `output_schema` gets named lines, with `glId` for Mifos and `comments` for the email
- The prompt's examples are rewritten into it. Their content is unchanged

### 7. The form as the email it used to be

- ourfos-v2's model read the form's notification email. We render the clean requisition the same way
- So the prompt's examples still fit, and lifting it stays a lift

### 8. `check` holds the model to the amount

- Debits must add up to the requisition's `amount`, within a cent, or the run hands over
- The prompt says to trust the form's amount. This makes that a rule, not a hope
- A cent, because the NSSA split rounds each half up

### 9. A static bearer token, for now

- Better than a public trigger, and the form's webhook and Postman both send a header
- One shared secret: anyone holding it can start a run, and it's only rotated by hand
- Secret Manager, owned by infra with secret-level grants (phase 4 ADR 7). A plain env var on dev if that costs more than it should
- **Revisit** before prod: a token per caller, or our front end's own identity

### 10. The submitter is stored, not logged

- `submitted_by` is who the emails go to later
- Phase 3 ADR 8 and phase 4 ADR 8 hold: the document has it, logs don't

### 11. Dev only, still

- Phase 4 ADR 10 holds. The shape settles here, but attachments, Workspace and Mifos still aren't real
