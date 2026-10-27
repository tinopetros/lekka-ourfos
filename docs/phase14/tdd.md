# Phase 14: submit-forms

## Goal

- Every form submitted from the UI, typed, on a page that becomes the record, with drafts saved as you go
- Test submissions for those the policy names: the first permission
- Google Forms retired, form by form, once ours have launched well (ADR 1)

## Steps

One PR, a commit per step.

1. **Statuses, and strict forms** (ADR 2, 3, 4)
   - Every form but requisitions shows a grey **Received**. Display only
   - Each form's model typed, every field with a title, and a description where it needs one. The text forms' `labels` give way to the models' fields; the old labels stay, for old submissions
   - The vehicle log reshaped (below)
   - Pydantic → OpenAPI → zod, in `make types`, checked in CI
2. **Submitting** (ADR 1, 5)
   - `POST /api/forms/{form}/submissions/{id}/submit`: the strict model, then one transaction: `received_at`, the response number from `counters/{form}`, `source: ourfos`, `submitted_by`. Then the workflow, with the argument the trigger gives it
   - The workflows save a submission that exists already, a draft's, as they do a new one
   - `ourfos-api@` starts each form's workflow, posting as `mifos.post` in each env's tfvars has it: off on prod
   - Submitting twice is submitting once: the second answers with the first's number, and starts the workflow only if the first couldn't
   - `counters/{form}`, seeded by the first submit that finds none
3. **Permissions** (ADR 9)
   - Every route declares its permission; a policy in code grants them, to people, the domain and groups
   - `forms:{form}:read` and `:submit` to everyone, `forms:*:test` to `tech@`, `journal_entries:read` to `directors@`
   - Groups from Cloud Identity, nested too, kept 5 minutes
   - `/me` lists yours; the UI hides what you can't do
4. **The form page** (ADR 6)
   - `/forms/{form}/new`, from **Create** on each list and on home
   - Drawn from the schema: a field per kind, its title and description, required ones marked. react-hook-form, zod's resolver, shadcn's form fields
   - **Test**, a switch, for those allowed
   - A question with one answer has it already; a trip's date starts at today; a client folder's question has a picture of where to find it
   - Files wait for step 5: they're uploaded as they're picked, under the draft's id
   - Errors by each field, and a summary at the top on submit
   - Submitted, it's the record's page, as any other
   - Toasts for an action that fails: `MutationCache`'s `onError`, shadcn's Sonner
5. **Drafts** (ADR 7, 8)
   - `PUT /api/forms/{form}/submissions/{id}`: the whole draft, every field optional. Refused once submitted, or someone else's
   - `DELETE` the same: discards a draft, and its files
   - `POST /api/forms/{form}/submissions/{id}/files`: an upload, to `gs://<attachments>/{form}/{id}/`
   - `GET /api/forms/{form}/drafts`: yours, newest first
   - Saved when you leave a changed field; the URL becomes the record's on the first. "Saving…", "Saved"
   - **Your drafts** above each list
   - A lifecycle rule on the bucket clears a discarded draft's files

## The forms

Titles first; a description after, where there is one. Required ones marked *.

Amounts are USD, to 2 decimal places.

**Requisition**: Payable to\*, Amount\*, Disbursed on (date), Reference number ("The number on the paper requisition, if it has one"), Comment, Signed requisition form, Receipts, Invoices (files)

**Vehicle log**
- Vehicle\* (a choice, the Google Form's list)
- Date\* (today by default)
- Purpose\*: "Where to, and why"
- Odometer at start\*, Odometer at end\* (whole numbers, the end not below the start)
- Odometer photos (files)
- Vehicle photos (files): "Of anything worth a record: damage, a warning light"
- Comment: "Anything else: refuelling, fuel readings, repairs or checks, issues with the vehicle, other drivers, a trip over more than a day. Fuel and repairs that cost money go in a requisition"

**Loan approval**
- Applicant's first name\*, last name\*, other names
- Character: "What's your assessment of the client's character?"
- Purpose: "What is the facility for?"
- Loan amount, Tenure (months), Monthly repayment (worked out by ourfos later: #39)
- Ability to repay: "Include cover ratio, salary, profit details, etc."
- Borrowing status: "Other loans, with us or elsewhere: tenor, amount, disbursement date, etc."
- Security vetted (yes or no): "Has the security been vetted, and does it meet the assessment guidelines?"
- Referred by
- Recommendation (approve or decline): "Yours, personally"
- Overall assessment: "Anything else the approvers should know?"
- Client folder (a Drive folder's link): "In Drive, Shared with me › Client Folders: right-click the client's folder, then Share › Copy link", with a picture of where, on hover. Client folders in ourfos later: #40

**Write-off**
- Client's first name\*, last name\*, other names, as a loan approval's
- Client number, Loan account number
- Original principal, Total recovered, Current balance (amounts)
- Loan term (months), Outstanding instalments (a whole number)
- Reason
- Justification: "Why should it be written off?"
- Supporting documents (files)

## Local

- `make web` as before. A submission from local is dev's, numbered below zero, and starts dev's workflow

## Tests

- The API: submit numbers once and starts once, a draft's save after submitting is refused, someone else's draft is refused, test needs its permission, uploads only under their submission
- The UI: a form drawn from a schema, errors by the field, saves on leaving a field and in order, the URL becoming the record's

## Smoke

- Unchanged this phase: the trigger, with `?test=true`, starts real workflows on dev
- Once the Google Forms close, smoke submits through the API instead, the path people use: a test submission, as a smoke account the policy lets submit tests. It waits on a build signing in to IAP (phase 13); until then, smoke starts the workflows directly
- Unit tests stay as they are, against fakes. Smoke checks the deployed whole

## Bootstrapped, once

- Infra: `ourfos-api@` starts workflows, and writes to the attachments bucket beside #21's read (tinopetros/lekka-ourfos-infra#22); Cloud Identity's API (#23)
- Admin console: **Groups Reader** for `ourfos-api@` in each project. Done Oct 27
- Each Google Form closed, its counter seeded, once its UI form has launched well
