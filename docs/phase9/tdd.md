# Phase 9: we send the emails

## Goal

- Every email about a requisition is ours: the first one, on receipt, then a reply in the same thread with the classification or the handover
- The form add-on stops emailing. Nobody should notice the switch but for the sender
- Once Mifos is real, a third email confirms the post and is the final word (phase 1 ADR 2)

## Shape

```
form ─▶ trigger ─┬─ clean ─▶ workflow ─▶ receive ─▶ acknowledge ─▶ classify ─▶ check ─▶ notify ─▶ post … confirm
                 │                                     │ first email: the thread        │ reply: the suggestion
                 └─ can't clean ─▶ workflow ─▶ handover: a new email, with what the form sent
                                     any failure ─▶ handover: a reply, or a new email if there's no thread yet
```

- `receive` stores the requisition, as today. `acknowledge` is new: it sends the first email and returns the thread
- `get_thread` goes, with `/thread`, its wait of up to four minutes for a late Forms email, and the `ThreadMissing` fail-red path (ADR 1)

## The emails

All from `lekkai@`, HTML with a plain-text alternative, built in `services/emails.py`. Every value from the form is escaped: the payee and comment are free text

### Received

What the form add-on sends today, from its "All Answers":

- **Your form Requisition Approval Request Form has a new entry from {submitted_by}.**, in bold like the reply's suggestion
- A two-column table: Email address, Payable To, Total Amount, Date Disbursed, Comment, then a row per file field with files: Signed Requisition Form, Receipt(s), Invoice(s). A field left empty has no row, as today
- "Sep 18, 2026" for dates. The amount as the form had it: 60, or 1,234.50
- Files as "File 1", "File 2", each a link to Drive (`drive.google.com/open?id=…`). A `gs://` file is named without a link until the front end can show it (ADR 4)
- Sender's name: the form's

### Classified

ourfos-v2's reply, as the accountants know it:

- **Lekkai's Suggestion: APPROVE** or **DEFER**, then the reason
- The table: Account, GL Code, GL ID, Account Type, Debit, Credit. A rejection has no lines, so no table
- The comments as bullets
- *Lekkai is an experimental AI agent at Lekka, it may make mistakes...*
- Sender's name: Lekkai

### Handed over

- **Lekkai handed this over: it needs a person**, then the reason the workflow gives, e.g. which file couldn't be fetched
- When the form couldn't be read: what the form sent, as sent, so a person can see what was wrong
- Sender's name: Lekkai

### Posted

- Not while Mifos is a stub: `confirm` records nothing and sends nothing. An email confirming a post that didn't happen would be a lie (ADR 6)

## Subject and thread

- `{FORM_NAME} - {payable_to} - #{response_number}`, the same on every email of a requisition. `FORM_NAME` is an env var: the name of whatever comes through this workflow, whether the form or later the front end posted it
- Gmail threads a reply by its thread id and a matching subject. Recipients' clients thread it by `In-Reply-To` and `References`. Every reply sets all three, pointing at the first email
- The first email's `Message-ID` is read back once, with `gmail.readonly`, which `lekkai@` already has
- A person replying before Lekkai does doesn't matter: ours still points at the first email, in the same thread
- `acknowledge` returns `{thread_id, in_reply_to}`. The workflow hands it to `notify`, `confirm` and `handover`, so a handover never needs the database for it (phase 4 ADR 2)

## Recipients

- To: the project's list and the submitter, once each
  - `NOTIFY_TO`, a comma list per project from Terraform's `notify_to`
  - Prod: `lekkai@`, `directors@`, `consultant-zsaruchera@`
  - Dev: `lekkai@`. A manual submission on dev reaches whoever submitted it too
- Only our own domain, the one `lekkai@` is in: any other address is dropped and counted in the logs, never mailed (ADR 3)
- **Revisit** with an admin UI: the list moves to a config document the service reads

## One send per kind

- Each email is stored as `emails.<kind>`: `received`, `classification`, `handover`. Before sending, the service looks: if this run already sent that kind, it answers with what's stored and sends nothing
- So a send that landed but answered late, then retried, isn't a second email
- The gap: Gmail sends, then the store's write fails, then a retry sends again. Rare, and a duplicate email at worst: accepted
- `handover` checks too, but sends anyway if the database can't be read: someone has to hear

## A form the trigger can't clean (ADR 5)

- Today the add-on emails every submission, even one we then refuse. With the add-on off, a 400 from the trigger would tell nobody
- So the trigger starts the workflow anyway, with `invalid` (the problems, never the values) and the form's `raw` payload, and still answers 400 with the problems and the execution id
- The workflow goes straight to `handover`. Nothing is received, classified or posted: `requisition` is null
- The email goes to the list, and to the submitter if the payload has an address in our domain. Its subject uses the payee and response number when there are any
- A missing token, `?workflow=`, or a body that isn't JSON still just answers 401 or 400: nothing to email about, or nobody it's from

## Code

- `integrations/workspace/gmail.py`: `send(to, sender_name, subject, html, text, thread=None)`. `messages()`, `thread()` and `send_to_self()`, phase 6's setup check, go
- `routers/gmail.py` and `make workspace` go: a real email is now the check
- `integrations/workspace/stub.py` goes. Fixtures still force failures with `simulate`, before the real send: `acknowledge`, `notify`, `confirm`
- `store.record` keeps `thread_id` and `emails.<kind>`: `{message_id, at}`

## Fixtures and evals

- Every fixture's submitter becomes `lekkai@`, and so does every eval case's. Smoke's emails only ever reach `lekkai@`
- `thread-missing` goes. `acknowledge-fails` is new: no thread, so the handover is a new email
- `invalid` is new: an amount the cleaner refuses. Smoke expects its 400, then `handed_over`
- Smoke is five runs now, about ten emails per merge, all to `lekkai@`

## Terraform

- `ourfos-services`: `NOTIFY_TO` from `var.notify_to` in `env/<env>.tfvars`, and `FORM_NAME`
- The scopes stay phase 6's: `gmail.send` to send, `gmail.readonly` for the first email's `Message-ID`

## Bootstrapped, once

- Prod: turn off the add-on's notification when the tag with this goes out, not before, or nobody hears; not long after, or everyone hears twice
- Dev: nothing. The add-on only mails prod's list

## Done when

- `make test` covers the subject, the recipients and their domain, escaping, and each email's parts and headers
- On dev, smoke passes, and `lekkai@`'s inbox has a thread per run: the first email and one reply, threaded
- A manual submission on dev reaches me and `lekkai@`, in one thread

## What execution changed

## Not in this phase

- Reading replies: the thread id is stored, so it's one `threads.get` when we want it
- The posted email, with Mifos
- Viewing `gs://` files from an email (ADR 4)
- Recipients in an admin UI
