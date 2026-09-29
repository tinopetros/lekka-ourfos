# Phase 9: decisions and shortcuts

### 1. We send the first email

- The form add-on sent it, so we had to find its thread before replying: a Gmail search, a wait for a late email, and a way to fail that only existed because the email wasn't ours
- Now `acknowledge` sends it and keeps the thread. This closes phase 1 ADR 1 and phase 6 ADR 5
- Replies, updates and, later, reading replies are all on a thread we already know

### 2. It looks as it does today

- The same subject, `{form name} - {payee} - #{response number}`, the same answers table, the same reply as ourfos-v2
- The first email names the form as its sender, as the add-on did. Gmail shows `lekkai@`'s picture, not the add-on's: a second sending account would widen phase 6's delegation for a picture

### 3. Recipients are config, and only ours

- The list is an env var per project: people change, the code shouldn't. **Revisit** with an admin UI
- `lekkai@` is on it, so its inbox holds every thread
- The submitter comes from a request, so only an address in `lekkai@`'s own domain is mailed. The same reasoning as phase 7 ADR 2's bucket

### 4. Files in GCS get a link through the front end

- For when files move to GCS. A signed URL can't go in an email: it lasts a week at most, and emails are kept for years. Staging copies in Drive means two stores and a clean-up
- So one stable link per file on the front end, which checks who's signed in and redirects to a short-lived signed URL. The browser shows a PDF or an image in a new tab
- Until then only Drive files are linked, and every form file is on Drive. A `gs://` file is named, unlinked
- **Revisit** with the front end

### 5. A form we can't read is handed over

- With the add-on off, a submission the trigger refuses would email nobody
- The trigger starts the workflow anyway, and it hands over at once: one path to email anyone, and the submitter hears, when the payload has their address
- The trigger still validates: nothing unclean is received, classified or posted
- Not taken, for now:
  - **Alert only**, on the trigger's 400s in the logs. Reaches me, not the submitter, and it's a second channel
  - **The trigger emails** the list itself. A second place that sends email, with its own delegation
- **Revisit** if refused payloads ever carry something we'd rather not email, or come from somewhere other than our form

### 6. No posted email until Mifos

- The post is a stub, so a confirmation would confirm nothing. Two emails a requisition for now; three with Mifos, the last replacing the suggestion as the word that counts (phase 1 ADR 2)

### 7. One send per kind, not exactly once

- A stored `emails.<kind>` stops a retried send. A send whose write then fails can still send twice: a duplicate email is the worst of it
