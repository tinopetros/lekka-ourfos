# Phase 14: decisions and shortcuts

### 1. Our own forms, and Google Forms retired

- Every form is submitted from the UI. Each Google Form closes once its UI form has launched well, then the trigger goes
- One path in: the API saves the submission, then starts the workflow the trigger would, with the same argument
- Until a form's Google Form closes, the trigger keeps taking it, through what that Google Form sent: its own model, beside ours (`google_form` on each form)
- `source` on each submission: `ourfos` or `google-form`. `submitted_by` is who's signed in, never the request body
- The cost: the risk sits with us. Google Forms took the uploads, the validation and the numbering, and never went down. Running both a while is the fallback, one form at a time
- Not taken: **keeping Google Forms beside ours**. Two ways in, two sets of rules, and response numbers that collide (ADR 5)

### 2. Only requisitions show a status

- Every other form shows a grey **Received**: all ourfos knows of it. Where it stands happens in its email thread
- Display only, by `tracks_status` on each form, which `/api/forms` passes on. Firestore keeps `status`, the intake run's own (`done`: acknowledged; `handed_over`: not), which is true of the run, not of the request
- Requisitions keep theirs, a reminder that each form's status belongs in ourfos. A form's badge comes back when ourfos tracks where it stands

### 3. Strict types, from Pydantic to the form

- Each form's model says what it takes: amounts, whole numbers, dates, choices, links, files. The text forms were all text since phase 10, strict only where the subject needs it; no longer
- Each field has a short **title**, and a **description** where it needs more: the long questions become descriptions, and keep their short titles. Both on the Pydantic field, which the emails, the record's page and the form all read
- An amount is USD, at least 0, to 2 decimal places: a number, as a requisition's is today. Another currency is its own change
- Pydantic → each form's JSON Schema, generated with the types into `web/src/lib/api/forms.json`, and CI fails when they drift. The browser makes zod from it, with zod's own `fromJSONSchema`: the form checks what the API will. TypeScript's types are gone at runtime; zod checks what's typed into the form, and react-hook-form shows its errors by each field
- `kind` on a field says how to ask what its type can't: long text, an amount, files. A check across fields, like the odometer going forwards, is the API's alone: its error comes back to the field
- The form is drawn from the schema: a field per kind (text, long text, amount, number, date, choice, link, files), in the model's order. Adding a question is a backend change only. A form that needs more gets its own component
- Old submissions keep their answers as they were: the view keeps every label they've had
- Not taken: **a zod schema per form by hand**, a second definition to drift; **zod generated from OpenAPI** (orval, hey-api), another generator for what one function does; **a form per page by hand**, for questions that are all one of a few kinds

### 4. The vehicle log, as short as a requisition

- Vehicle, date, purpose, odometer at the start and the end, their photos, the vehicle's photos, and a comment
- Driver is who's signed in. A trip is one day. Distance is worked out
- Fuel readings, refuelling, repairs, issues and other drivers go in the comment, and its description says so. Fuel and repairs that cost money are requisitions
- From 21 questions to 8

### 5. ourfos numbers its submissions, when they're submitted

- Google Forms numbered them; nothing else does now. A counter per form, taken in the submit's transaction, so no two share a number
- Prod counts up from the highest it holds. Dev counts down from -1: a dev submission in an inbox is plain to see
- A draft has no number until it's submitted: it sends no emails
- `counters/{form}` in Firestore, `{next}`. Seeded by the first submit that finds none, in its transaction: one past prod's highest, -1 on dev. No script
- So a form's Google Form closes before its first submission from the UI on prod. Before, the two would hand out the same numbers

### 6. One page, from new to the record

- `/forms/{form}/new` mints the submission's id in the browser. The first save makes it `/forms/{form}/{id}`: the same page, now the draft's, and the record's once it's submitted
- While that page is open, it stays the form you're typing in as its URL changes. Opened again, or reloaded, a draft comes from the API: never a blank form over a saved draft
- An id from the browser makes every save safe to retry: a double click or a flaky connection never makes two. It's what an offline queue needs (#30)
- Single page forms for now. Steps, or a form in a modal, later

### 7. Drafts, saved as you go

- A draft is a submission with `status: draft`, its answers as typed in `draft`, and no `received_at`: lists order by `received_at`, and Firestore leaves out what lacks it, so drafts keep out of lists on their own
- Saved when you leave a question you've changed, or pick a choice or a file: the whole draft each time, one record's saves in order (TanStack Query's mutation `scope`), so a slow save never overwrites a later one. "Saving…", "Draft saved" by the title. A new form's own prefilled answers aren't worth a draft
- And on **Save draft**, and as the page goes: hidden, saved the usual way; closed, sent with `keepalive`, which the browser finishes after the tab's gone. Not as you type: a save a keystroke is too much
- Actions are coloured by what they do: Submit green, Discard red, Save draft neither. Drafts are amber, waiting on you to submit or discard them
- A draft takes anything, every field optional. The strict model is the submit's, and it never stops a save
- Each save is also looked over by the strict model, and answers with what submitting would find wrong: shown on the questions you've been to, or all of them on **Save draft**. One set of rules, the API's, those across fields too, like the odometer going forwards. The browser's own checks, from the schema, show at once; the rest a save later. Offline, only the browser's
- Not taken: **the cross-field rules declared for the browser too**. Instant, but a rule language of our own, two implementations of it, and only for what it can say
- Only its author sees a draft, above the list as **Your drafts**, and may discard it, its files too. Anyone else gets a 404. The first list that depends on who's asking
- Submitting is once: a transaction that turns the draft into a submission, numbers it and sets `received_at`, then starts the workflow. A save after that is refused
- Not taken: **drafts in the browser only**. Cheap, but lost with the browser, and never the page that becomes the record

### 8. Uploads through the API

- A file is uploaded as soon as it's picked, not on submit: the browser sends it to the API, its bytes the body, which writes it to the attachments bucket under `{form}/{id}/` and returns its `gs://` ref, saved into the draft. The first file makes the draft, if nothing else has The browser never talks to GCS: the API does, behind IAP, as it does reading them back (phase 13 ADR 14)
- A submission names only files uploaded to it: never another's, nor Drive's
- A draft's files stay until it's discarded. One left forever keeps its files: a clean-up of old drafts, when there are enough to matter. A bucket lifecycle rule can't tell a draft's files from a submission's
- The cost: a file through Cloud Run, 25 MB at most, under Cloud Run's 32. Photos and PDFs are well under
- Not taken: **signed URLs**, phase 13 ADR 11's plan. The browser writes to GCS itself, through a link the API signs. A link that writes for anyone holding it, and the API's account able to sign as itself

### 9. Permissions start here, by group

- Every route declares what it needs, e.g. `forms:requisition:submit`. Everyone at lekkacredit.com reads and submits forms; `tech@` sends tests; `directors@` reads every journal entry. A submission's page still shows its own entries to whoever may read the form
- The policy is code in the repo: a permission to people, `user:…`, a domain, `domain:…`, or groups, `group:…`
- Groups come from Cloud Identity as you're seen, nested ones too, kept 5 minutes. `ourfos-api@` reads them as **Groups Reader**, an admin role assigned in the Admin console. Walked up a level at a time: the one call that finds nested groups is Enterprise only. A lookup that fails grants nothing, and is tried again in 30 seconds
- Not taken: **syncing groups onto `users`** (phase 13 ADR 11). A job to run and a copy to go stale, for what a lookup a person every 5 minutes does
- `/me` lists your permissions: the UI offers only what you may, **Test** and the journal among it, and a section with nothing left in it goes. The API checks either way
- A test submission is as a test from a Google Form's link: no posting, and marked in its emails and the UI
- Not taken, yet: **editing the policy in the UI**. It moves to Firestore then, with every change recorded, and loses a PR's review

### 10. What comes after

- Multi-page forms, and forms in a modal
- Each form's status in ourfos, and actions on it: approving a loan, a write-off
- Permissions by group, and editing them in the UI (phase 15)
