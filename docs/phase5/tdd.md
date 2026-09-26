# Phase 5: real world data

## Goal

- Take the form's webhook payload as it really arrives, clean it at the trigger, and let only the clean shape through
- Classify with the real prompt and chart of accounts, lifted from ourfos-v2, minus everything that needs attachments
- At the end, the data flow is settled. What's left is Workspace and Mifos for real

## Shape

```
form / Postman ─▶ trigger ─ clean ─▶ workflow ─▶ /requisitions/{id}/… ─▶ expenser (real prompt)
                              │
                              400, no execution
```

- The trigger is the only place that knows about the form. Everything after it sees one clean requisition
- The workflow's steps, statuses and handover are phase 4's. Only what flows through them changes

## What the form sends

The webhook maps each answer to a key. Every value is a string:

| Key | From | Example |
| --- | --- | --- |
| `response_number` | Response Number | `"482"` |
| `response_id` | Response ID | Google's id for the response |
| `response_date` | Response Date | format to be pinned |
| `form_id`, `form_name` | Form Id, Form Name | `"Requisition Approval Request Form"` |
| `submitter_email_address` | Submitter Email Address | `"ltanga@lekkacredit.com"` |
| `payable_to` | Payable To | `"City parking"` |
| `total_amount` | Total Amount | `"611.23"`, maybe `"$1,200.00"` |
| `date_disbursed` | Date Disbursed | `"Apr 10, 2026"`, format to be pinned |
| `comment` | Comment | free text, often empty |
| `signed_requisition_form`, `receipts`, `invoices` | File uploads | Drive links, see below |

- **Files:** ourfos-v2 read these as HTML anchors, `<a href='https://drive.google.com/open?id=…'>File 1</a>`, one per file. We pull every Drive id out whatever separates them: anchors, commas, bare links, `open?id=` or `file/d/`. Duplicates dropped, order kept
- The formats marked "to be pinned" are pinned by the first real payload we capture (see Testing). Until then the cleaner accepts only what can't be misread

## The clean requisition

```
requisition
  response_number   int
  response_id       str
  form_id           str
  form_name         str
  submitted_by      str, lowercased
  submitted_at      datetime, with its zone. Africa/Harare when the form gives none
  payable_to        str, trimmed
  amount            float, > 0, currency signs and thousands commas dropped
  disbursed_on      date
  comment           str, or absent when empty
  files             { signed_requisition_form: [ids], receipts: [ids], invoices: [ids] }
```

- One pydantic model, `Requisition`, is the shape: the trigger builds it, `receive` validates it again, and the service and expenser read it through it. Dates are `date` and `datetime` in code, never strings
- On the wire, the workflow's JSON, they're ISO 8601, since JSON has no date type. The model parses them back, so a string never passes for a date
- In Firestore, `submitted_at` is a Timestamp. `disbursed_on` is `"YYYY-MM-DD"`: Firestore has no date, and midnight Harare as a Timestamp reads as the day before in UTC
- `requisition.py` lives in `services/`. `make package` copies it into the trigger's zip, as `stage` does expenser into the image
- Required: `response_number`, `response_id`, `submitted_by`, `payable_to`, `amount`. Anything else missing is left out, not guessed
- A date the cleaner can't read without guessing, like `04/05/2026`, is a 400, not a guess
- A 400 lists every problem at once: `{"errors": ["total_amount: not a number", …]}`
- Unit tested with pytest, in `make check`. The cleaner is the one piece of this phase with real branching and no GCP in it

## The trigger

```
POST /
  { …the form's keys…, "simulate": {…} }   simulate: dev fixtures only, the workflow drops it in prod
```

1. Pops `simulate`, cleans the rest. Problems: 400, nothing started
2. Starts the workflow with `{requisition, raw, simulate}`. 202 with the execution id, as now

- `raw` is the body as posted, minus `simulate`. `receive` stores it next to the clean one
- Still public, as in phase 2
- Logs the execution id and `response_number`. Never the body

## Classify

- `agents/expenser/`:
  - `prompt.py`: ourfos-v2's prompt, lifted
  - `accounts.csv`: its chart of accounts, as it was
- The same sections: role, tone, task, exceptions, examples, chart of accounts
- **Taken out**: every bullet about the attached requisition, signatures and receipts, and "disapprove any expense without a requisition attached". In their place, one line: attachments aren't shown yet, so never reject over one; judge from the form
- **Kept**: the salary refusal, the PAYE/ZIMDEF/NSSA rules, the NSSA split, "credit is Cash at Vault unless the form names a bank"
- **Swapped**: the FORMAT section for our `output_schema`. The examples are rewritten into it
- The model gets the clean requisition as JSON, as it does today. Not ourfos-v2's email
- So the prompt's examples are rewritten on both sides: our requisition in, our classification out. What they teach doesn't change
- The prompt's wording about "the email" becomes "the requisition"

### The classification

```
approve    bool
reason     str, the journal's description
debit      [{ name, glCode, glId, accountType, amount }]
credit     [{ name, glCode, glId, accountType, amount }]
comments   [str], why
```

- `glId` is what Mifos posts to. `glCode` is what a person reads
- `stub` answers in the same shape, with real accounts: an expense line against Cash at Vault
- The Mifos stub's read-back echoes the posted lines, so `verify` compares like with like

### What `check` adds

- Debits add up to the requisition's `amount`, within a cent. A model that invents or drops money hands over
- A cent, not exact: the NSSA split rounds each half up

## Statuses

Unchanged: `received → classified → posted → done | rejected | handed_over | failed`

- The salary refusal and anything else the model won't approve end `rejected`, with its reason
- A payload that fails cleaning never gets a document. The caller has the 400

## The document

Phase 4's, with:

```
requisition     clean, as above
raw             the form's payload as posted. This phase only
classification  approve, reason, debit, credit, comments
mifos_transaction_id   was transaction_id
```

- `transaction_id` becomes `mifos_transaction_id` everywhere: the document, the workflow's variables, step bodies and `/read-back/{mifos_transaction_id}`. Mifos's journal entry API calls it `transactionId`; the name is revisited when Mifos is real

- `submitted_by` is kept: it's who the emails go to later. Stored, never logged

## Emails

- `notify` already passes the whole classification to `workspace`. It now has comments and account names, so a real email has what it needs
- Rendering the email stays with the Workspace work: the requisition service builds it from the document then

## Terraform

- Nothing new. Infra neither

## Fixtures and smoke

- Every fixture becomes a form payload: string values, anchors for files. `simulate` stays beside it
- `happy`: the prompt's own City parking example, for 1. The model approves it
- New:

| Fixture | simulate | Ends | Why |
| --- | --- | --- | --- |
| `salary` | none | `rejected` | the real prompt's refusal |
| `nssa` | none | `done` | two debits, halves rounded up, still within a cent |
| `bank` | none | `done` | a comment naming ZB Bank moves the credit |
| `classify-jailbreak` | none | `handed_over` | the injection moves into `comment`, the new free text |

- `salary`, `nssa` and `bank` call the model, so they're for checking by hand, not smoke
- Smoke is unchanged: happy, jailbreak, 400.

## Testing by hand

```bash
make test                          # the cleaner
make run FIXTURE=happy
make doc ID=<execution_id>
```

- Postman against the dev trigger: a form payload 202, with `total_amount: "abc"` 400
- **One real payload:** point a copy of the form's webhook at the dev trigger and submit once. That pins the date formats and the file fields, and becomes a fixture, scrubbed

## Done when

- The cleaner's tests pass, including every file-field shape we know of
- Every phase 4 fixture, as a form payload, ends as before on dev, and `make doc` shows the clean requisition and `raw`
- `happy` ends `done` with Cash at Vault credited. `salary` ends `rejected`. `nssa` and `bank` look right by eye
- Postman gets 202 on a form payload and 400 on a bad amount
- Smoke passes on the dev build after merge

## Not in this phase

- Attachments: fetching files from Drive, and the prompt's rules about them
- Tuning the prompt, or choosing the model. That's the evals phase
- Real emails, real Mifos
- Knowing the source, so our own front end skips cleaning
- Authenticating the trigger
- Prod
