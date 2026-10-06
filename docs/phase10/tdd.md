# Phase 10: three more forms, received and acknowledged

## Goal

- The vehicle log, the loan approval request and a new write-off request come through the same trigger, services and database as requisitions
- For now each is only received and acknowledged: stored, and the first email sent, as the form's add-on sends it today. Whatever each form's own workflow does comes later
- What we store is ready for that: a submission is one document, and every workflow run on it, today's or a later approval or reversal, is a document of its own under it
- The requisition workflow becomes `expense`, for what it does. Its behaviour doesn't change

## Shape

```
vehicle log   ─┐
loan approval ─┼─▶ trigger ─▶ intake  ─▶ receive ─▶ acknowledge
write-off     ─┘      │
requisition ──────────┴────▶ expense ─▶ receive ─▶ acknowledge ─▶ classify ─▶ … (as phase 9)
                                any failure ─▶ handover, as phase 9
```

- One submission, one run: the trigger starts the form's workflow and answers 202, as today. Receipt is shared code in the services, not a run of its own that starts another (ADR 1)
- `intake` is one workflow for all three forms. A form gets its own when it gets steps of its own, as requisition did
- The workflows share their plumbing, `call_service`, `handover`, `complete` and the retry predicates, from one file Terraform puts under each (ADR 2)

## Names

| Form                              | `?workflow=`    | Collection       | Workflow  | Sender name |
| --------------------------------- | --------------- | ---------------- | --------- | ----------- |
| Requisition Approval Request Form | `requisition`   | `requisitions`   | `expense` | the form's  |
| Vehicle Log Form                  | `vehicle_log`   | `vehicle_logs`   | `intake`  | the form's  |
| Loan Approval Request Form        | `loan_approval` | `loan_approvals` | `intake`  | the form's  |
| Write-off Request Form            | `write_off`     | `write_offs`     | `intake`  | the form's  |

- `?workflow=` stays what the form's webhook sends, so no prod form is edited for the rename. It names the form now, and the trigger picks its workflow. Misnamed, and left so
- Runs are named for what they do: `intake`, `expense`, later `approve`, `reverse`

## What we store (ADR 3)

```
requisitions/{submission}                      the form's answers, raw, test, thread, emails.acknowledgement, status
requisitions/{submission}/runs/{execution}     workflow, status, reason, classification, emails.<kind>, execution
```

- `{submission}` is the form's own `response_id`. The execution id names the run, as it named the document before
- The submission holds what was submitted, once: `answers` (the clean one), `raw`, `test`, `response_number`, `submitted_by`, `submitted_at`, `form`
- The thread is the submission's: every run on it, a later approval or reversal too, replies in the same thread. So `acknowledge` sends the first email once per submission: a second run finds the thread and sends nothing
- Everything else is the run's: its status, what classify said, what was posted, its suggestion, handover and confirmation emails
- The submission's `status` is its latest run's, with `run` naming which, so a list of submissions needs no second read. How a run ended is still final (phase 4 ADR 4): a late write can't move a run's status, nor so the submission's
- A form the trigger can't clean is stored under its `response_id` when it has a usable one, otherwise under the execution id, with only `raw`
- Fixtures all say `response_id: "fixture-response"`. `make start` gives each run its own, `fixture-<fixture>-<time>`, or every run after the first would find the thread and send no first email
- The services' paths name the submission, `/forms/{form}/{submission}/…`. The run is the `X-Execution-Id` header `call_service` already sends

### From when

- The new shape started with 0.15.0, on 2026-10-01. Prod's 13 requisitions were rewritten into it that day, after a Firestore export to `gs://ourfos-prod-ourfos-sources/firestore-backups/before-reshape-2026-10-01`, with the script on PR #17. Dev's were too, as a trial

## Cleaning (ADR 4)

- Strict only where a step reads the value. The requisition cleaner doesn't change
- For the other three, strict: `response_number`, `response_id`, the submitter's address, `created_at`, and whatever the subject needs. Anything wrong there is a 400, handed over, as in phase 9
- Every other answer is text, trimmed, empty dropped. `$4000 over 6 months` stays `$4000 over 6 months`
- File uploads are Drive ids, as the requisition's: the vehicle's images, the write-off's documents. The loan's client folder is a link, kept as text
- Keys are the webhook's own, `refferer` and all. A key the form sends that we don't know is kept in `raw`, not in `answers`
- A field gets a real type when a step reads it, or when our own front end collects it typed

## The forms

The webhook's keys, the answers table's labels and their order, which is the form's, as the add-on's emails list them. Not the response sheet's: a question added later is its last column, wherever it sits on the form

### Vehicle log

- Subject: `Vehicle Log Form - {trip_name_purpose} - #{response_number}`, as the add-on's. Needs `trip_name_purpose`
- `trip_name_purpose` Trip Name / Purpose, `destination` Destination, `vehicle` Vehicle, `drivers` Driver(s), `purpose_category` Purpose Category, `trip_start_date` Trip Start Date, `trip_start_time` Trip Start Time, `trip_end_date` Trip End Date, `trip_end_time` Trip End Time, `odometer_start_reading` Odometer Start Reading, `odometer_end_reading` Odometer End Reading, `total_distance` Total Distance, `fuel_reading_start` Fuel Reading (Start), `fuel_reading_end` Fuel Reading (End), `was_refueled` Was the vehicle refueled at any point during this trip?, `was_fixed` Was the vehicle fixed / checked / maintained during this trip?, `was_fixed_description` Fix / Check / Maintenance Description, `issues` Issues, `issues_description` Issues Description, `comment` Comment, `vehicle_images` Vehicle Images (files)
- 87 responses, and five questions almost always "No" or empty. It shrinks with our own front end, not now

### Loan approval request

- Subject: `Loan Approval Request Form - {applicant_first_name} {applicant_last_name} - #{response_number}`, as the add-on's. Needs both names
- `applicant_first_name` Applicant First Name, `applicant_last_name` Applicant Last Name, `applicant_other_names` Applicant Other Names, `character_assessment` Character, `purpose` What is the purpose of the facility?, `loan_amount_and_tenure` Loan amount and tenure?, `monthly_repayment` What would be the monthly repayment?, `applicant_ability` What is the client's ability to service the loan?, `applicant_borrowing_status` What is the client's current borrowing status?, `has_security_vetted` Has the security been vetted…?, `refferer` Who referred the client, `submitter_recommendation` What is your personal recommendation e.g. "Approve/Disapprove", `overall_assessment` Overall assessment, `client_folder` Link to Applicant Client Folder
- Labels are the form's questions in full, as the add-on shows them
- Reply-To `directors@` and `lekkai@`, as the add-on's is `directors@`: a reply to a loan request goes to who decides it, and `lekkai@` keeps every thread

### Write-off request (new)

What Leon's two emails already set out, as questions. Mifos isn't real yet, so the figures are asked for, not read from it.

- Subject: `Write-off Request Form - {client_full_name} - #{response_number}`. Needs `client_full_name`
- `client_full_name` Client Full Name, `client_number` Client Number, `loan_account_number` Loan Account Number, `original_principal` Original Principal, `loan_term` Loan Term, `total_recovered` Total Amount Recovered, `current_balance` Current Account Balance, `outstanding_instalments` Outstanding Instalments, `reason` Reason (a choice: No longer employed, Ill, Deceased, Can't be reached, Other), `justification` Why should it be written off?, `supporting_documents` Supporting Documents (files, optional)
- The form checks the figures are numbers. The cleaner keeps them as text all the same
- Once Mifos is real, the client and loan numbers are what a later step reads the rest from

## Emails

- The acknowledgement is phase 9's for every form: **{form name} has a new entry from {submitter}:**, then its answers, empty ones left out, files as "File N" links
- The handover names the form's thing and who takes it: **Lekkai failed to process this {requisition, vehicle log, loan approval request, write-off request}: {an accountant, someone, a director, a director} needs to take it from here.**
- A form's name, list and Reply-To are Terraform's, one map for every form, `FORMS` for the services (it replaces `FORM_NAME` and `NOTIFY_TO`):

  | Form          | Prod                                                      | Dev                           |
  | ------------- | --------------------------------------------------------- | ----------------------------- |
  | requisition   | `lekkai@`, `directors@`, `consultant-zsaruchera@`         | `lekkai@`                     |
  | vehicle log   | `lekkai@`, `directors@`                                   | `lekkai@`                     |
  | loan approval | `lekkai@`, `directors@`; Reply-To `directors@`, `lekkai@` | `lekkai@`; Reply-To `lekkai@` |
  | write-off     | `lekkai@`, `directors@`                                   | `lekkai@`                     |

- Plus the submitter, our domain only, as phase 9. A test run goes to `lekkai@`, and the submitter if `test_to` lists them (release 1 ADR 3), and its Reply-To is `lekkai@` only

## Code

- `services/submission.py`: what every form has, `response_number`, `response_id`, the submitter, `submitted_at`. `Requisition` builds on it
- `services/forms.py`: the three new forms' models and every form's facts: collection, workflow, subject fields, labels, what to call it in a handover. The trigger's zip takes it, with `submission.py` and `requisition.py`
- `functions/trigger/form.py`: one text cleaner for the three, driven by `forms.py`
- `services/routers/forms.py`: `receive`, `acknowledge`, `handover`, `complete`, for every form. `routers/requisitions.py` keeps `classify`, `suggest`, `post`, `read-back`, `confirm`
- `services/store.py`: a submission and its runs
- `gmail.send` takes a Reply-To
- `workflows/lib.workflows.yaml`, `expense.workflows.yaml` (was `requisition`), `intake.workflows.yaml`

## Fixtures

- `workflows/fixtures/<form>/`: `requisition/` holds today's, each new form gets `happy` and `invalid`. Every one submits as `lekkai@`, response `-482`
- `make run FORM=vehicle_log FIXTURE=happy`. `FORM=requisition` by default
- Smoke adds each new form's `happy` (done) and `invalid` (handed over): six more runs, six more emails to `lekkai@`

## Bootstrapped, once

- The three forms' add-ons get the trigger's URL, `?workflow=<form>`, and `Authorization: Bearer <trigger-token>`: on dev, then on prod once the tag is out. The write-off form is made on both first, with the questions above
- Each add-on's own email notification, the one ours replaces, stays on through all of it. Two first emails for a while beats none
- It goes off, form by form, only once our first email has been seen arriving for a real submission of that form

## Done when

- `make test` covers the text cleaner, every form's subject, acknowledgement and handover, and the Reply-To
- On dev, smoke passes: requisition's six as before, and each new form's `happy` and `invalid`
- A requisition's document is its `response_id`, with one run under it; a second run of the same fixture id replies in the first's thread
- A manual submission of each form on dev reaches me and `lekkai@`

## Not in this phase

- What each new form's workflow does next: an approval by a director, a write-off in Mifos, a vehicle log that's two taps
