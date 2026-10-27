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
   - `ourfos-api@` starts the four workflows. `post_to_mifos` in each env's tfvars (ADR 10)
   - Counters seeded: prod's from its highest number, dev's at -1
3. **Permissions** (ADR 9)
   - Every route declares its permission; a policy in code grants them. `forms:{form}:submit` to everyone, `forms:{form}:test` to those named
   - `/me` lists yours
4. **The form page** (ADR 6)
   - `/forms/{form}/new`, from **Create** on each list and on home
   - Drawn from the schema: a field per kind, its title and description, required ones marked. react-hook-form, zod's resolver, shadcn's form fields
   - **Test**, a switch, for those allowed
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

**Requisition**: Payable to\*, Amount\* (money), Disbursed on (date), Reference number ("The number on the paper requisition, if it has one"), Comment, Signed requisition form, Receipts, Invoices (files)

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
- Loan amount (money), Tenure (months), Monthly repayment (money)
- Ability to repay: "Include cover ratio, salary, profit details, etc."
- Borrowing status: "Other loans, with us or elsewhere: tenor, amount, disbursement date, etc."
- Security vetted (yes or no): "Has the security been vetted, and does it meet the assessment guidelines?"
- Referred by
- Recommendation (approve or decline): "Yours, personally"
- Overall assessment: "Anything else the approvers should know?"
- Client folder (a link)

**Write-off**
- Client's full name\*, Client number, Loan account number
- Original principal, Total recovered, Current balance (money)
- Loan term (months), Outstanding instalments (a whole number)
- Reason
- Justification: "Why should it be written off?"
- Supporting documents (files)

## Local

- `make web` as before. A submission from local is dev's, numbered below zero, and starts dev's workflow

## Tests

- The API: submit numbers once and starts once, a draft's save after submitting is refused, someone else's draft is refused, test needs its permission, uploads only under their submission
- The UI: a form drawn from a schema, errors by the field, saves on leaving a field and in order, the URL becoming the record's

## Bootstrapped, once

- Infra: `ourfos-api@` writes to the attachments bucket, with tinopetros/lekka-ourfos-infra#21's read
- Each Google Form closed, its counter seeded, once its UI form has launched well
