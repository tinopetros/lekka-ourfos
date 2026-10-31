# Phase 15: decisions and shortcuts

No TDD: mostly UI on endpoints that were there. Release 1 ADR 4 (permissions stay in code) and 5 (names from the
directory) were decided this phase too; phase 16's notes hold what comes next.

### 1. A posting is undone from its requisition, by the correction workflow with no lines

- Reverse journal entry, on the requisition's live entry. The API checks the entry is still live and that there's a
  reason, then starts `correction` with no lines, as phase 12 built it. The mirror, its email and the run are as before
- The page watches the run, every 2s for up to 5 minutes, and toasts how it ended. The toasts are the mutation's, not
  the button's: the button goes once the entry isn't live, before the run ends
- A reason, always: the workflow refuses a correction without one, and it's what the thread is told
- `journal_entries:edit`: directors and consultant-zsaruchera@, as journal reads, and never lekkai@. Edit, not
  reverse, so whatever else is done to an entry later, e.g. correcting it, falls under it
- Not taken: **the API posting the mirror itself**. A second way to reverse, beside the workflow's retries and its
  "may have landed" guard

### 2. A correction ends `corrected` or `reversed`, not `done`

- A run's ending status is its requisition's, and a reversal ending `done` read like a posting that stood
- `corrected` (green) when new lines went live, `reversed` (red) when nothing's live. Both final, in `store.ENDED`
- Records from before keep `done`
- A mirror is told apart by `reverses`, not by its status, which is `live` as for any entry Mifos holds. The UI labels
  it "Reversal of …", and the original "Reversed by …". Nothing migrated

### 3. Journal entries are seen on their requisition; the journal itself needs `journal_entries:read`

- A requisition's Journal entries tab shows its entries to anyone who can read the requisition: they come with it
- The journal list, and each entry's own page, stay behind `journal_entries:read`. Without it, nothing links there:
  links to an entry's page are hidden, and point at the requisition's tab instead
- Not taken: **reading an entry because you can read its requisition**. One endpoint with two ways in, and care later
  for entries with no requisition, once the sync is back. Only the Details tab would be gained; reference and comments
  can go on the requisition's tab instead

### 4. A record page's tab is in its URL

- `?tab=`, so Back, a reload and a shared link open on it. Switching replaces the URL, so Back still leaves the page
- The arrows carry it to the next record, and Copy link includes it. A tab a record hasn't falls back to the first
- While a tab has focus, ← and → move between tabs, not records
- Not taken: **a route per tab**. One record, one fetch: tabs are views of it

### 5. Every email links its own tab on Ourfos, under its heading

- The intro to Overview, the suggestion to History, a posting, reversal or correction to the Journal entry tab, a
  handover to History. From `UI_URL`, which file links already used
- Under the heading, worded differently in each email: Gmail trims trailing content repeated through a thread
- What happened line by line, then its lines. The reversal shows the mirror's lines, as the page does
- A posting says who can undo it: "An accountant or director can reverse it on Ourfos"

### 6. Prod posts to the books

- Release 0.43.0: `post = false` gone from prod.tfvars. The Google Forms are closed, so no `&mifos=false` link is
  left
- A posting can be reversed from Ourfos (ADR 1); corrections with new lines are phase 16
- Test runs post too, to `demo` (ADR 8)

### 7. The trigger is retired

- The Google Forms are closed, so nothing calls it: our own form submits through ourfos-api, which starts the run
- Gone with it: its function, public URL and token, the cleaner of a Google Form's payload, and the workflows'
  `invalid` and `raw`. The API refuses an invalid form before any run starts, so a run always has its submission
- Fixtures are the workflow's own argument now, converted once by the cleaner before it went. `make start` hands one
  straight to the workflow, as `make correct` does. Smoke loses its token and `?workflow=` checks, and the invalid
  fixtures
- What the Google Forms sent is still read: their models stay, for the submissions they made
- Scheduler's sync jobs, none yet, run as `ourfos-api`, which already starts workflows. The infra repo drops
  `ourfos-trigger` and its sources bucket once this is on prod
- `trigger-token`, made by hand, is deleted by hand

### 8. A test run posts, to `demo`, on dev and prod alike

- Closes #44. A test run was the one real run that never reached Mifos, so prod's posting went untested. Now it posts
  to `demo` wherever it runs. Its emails still go to lekkai@ and its submitter only
- Each entry keeps its `tenant`, so a reversal or correction posts where the entry is. The UI says "(demo)" beside
  Live in Mifos, and the entry's Details tab names the tenant
- Prod is never smoked, by a build or the Makefile: Tino tests it by hand, on Ourfos, with test submissions
- Taken on trust, not checked yet: `demo` has the same GL account ids as `default` (expenser's CSV was checked
  against `demo` only), the same office id, and prod's Mifos user can sign in to it. Tino's first test submission on
  prod is the first check of all three
- The cost: prod's journal list shows test entries beside real ones, told apart by their tenant

### 9. ourfos-api reaches Mifos only through ourfos-services

- ourfos-api holds no Mifos credentials, read-only or not: ourfos-services stays Mifos's one go-between. Overrides
  phase 13 ADR 2 in part
- So ourfos-api may invoke ourfos-services, a blanket `run.invoker`, as Cloud Run can't grant one route. The API still
  decides what a user reaches, each route by permission
- The services narrow it themselves: called as ourfos-api, only `GET /mifos/accounts` answers, anything else is a 403.
  The caller is the ID token's email, which Cloud Run checked before the call reached us
- Writes only go through workflows: the API starts a run, it never calls a step such as `post`
- Not taken: **passing the user's identity through to the services.** They answer the same whoever asks. Revisit if
  they answer per person, or a third caller turns up

### 10. Corrections pick from Mifos's own accounts, kept in Firestore

- Correct journal entry, beside Reverse: the same workflow, with lines. The picker offers Mifos's postable accounts
  (detail, enabled, manual entries allowed), read live through mifos-connector 0.1.0. Partly #27: expenser still
  reads its CSV
- Kept on `mifos_accounts/{tenant}`, so restarts don't matter. They answer straight away, and once a day old are read
  again in the background, never blocking the dialog; a failed read leaves them standing. Only a tenant never read
  waits on Mifos. A refresh button in the admin section is #51
- An entry's own tenant, or the services' when it has none. Prod reads `demo` only to correct a test entry, as it
  posts there only for a test run (ADR 8)
- Not taken: **reading them only at startup.** We scale to zero, so that would be more often, not less

### 11. Google's APIs bill the caller's own project

- The directory and groups reads name no project to bill. On Cloud Run, ourfos-api@ bills its own, which takes no
  right. Naming one takes `serviceusage.services.use`, so every name lookup was a 403 and showed the email
- Locally, your ADC names its own, once: `gcloud auth application-default set-quota-project ourfos-dev`
- Not taken: **granting ourfos-api@ `serviceUsageConsumer`.** A right it needs only because the code asked for it

### 12. A name is asked for again after a week

- Names rarely change: a day asked the directory seven times as often for nothing. Overrides release 1 ADR 5 in part
- As before, a name saved stands when the directory can't say, and local reads dev's, so it falls back to it too

### 13. Tests are left out of lists, on dev and prod

- Submissions and the journal leave out tests: a test submission and its entries. Whoever may make them
  (`forms:<form>:test`, the journal by requisitions') can show them with Enable tests in lists (ADR 15), and
  previous/next on a record then walks the list it came from
- Left out by the API, which reads on until a page is full: filtered in the UI, a page could come back empty
- An entry says it's a test from now on. One recorded before is a test if its submission is, read with its page
- A record opened by its link still shows, test or not

### 14. Each Mifos post has a connection of its own

- A correction's lines went out 0.3s after its reversal, on the connection the reversal had used, and Mifos closed it
  without answering. Nothing landed, but a dropped post can't say so: the run was handed over, the books left without
  the expense
- So each post opens its own connection and closes it after. Reads keep one client a tenant, its connections reused
- Tried on dev, ten corrections in a row, before it went to prod. If it hadn't held, corrections would have gone
  behind a flag, leaving reversals

### 15. Feature flags, off until switched on in a browser

- What isn't for everyone yet sits behind a flag, named "Enable …": corrections, approvals and comments, tests in
  lists, and test submissions. Each is off on dev and prod alike until someone switches it on, for themselves
- Kept in the browser only, never in the database. The switches are on the build number at the sidebar's foot,
  underlined for whoever holds `features:edit`: tech, for now
- Through OpenFeature, the open standard, with its in-memory provider over the browser's storage. A provider that
  serves flags from elsewhere, per person or per environment, can take over without touching what reads them
- A flag hides, it doesn't grant: the API still checks each permission. A draft already marked a test keeps its
  switch while the flag is off, so it can be unmarked
- Corrections are behind one after a post Mifos dropped (ADR 14): reversals stay for everyone who may edit entries

Changed: corrections are live for everyone who may edit entries, and Enable corrections is gone (ADR 18).

### 16. Actions: done, approve, disapprove and comment, side effects first

- A person acts on a submission from its page's top row, each button named in full: Mark as done on a handed-over
  requisition (directors and zsaruchera, a comment required); Approve, Disapprove and Comment on loan approvals and
  write-offs; Disapprove on a requisition, which reverses its live entry first. All but Mark as done are behind
  Enable approvals and comments (ADR 15). Files can go with any, linked in the email by their ref, as form files are
- One workflow, `action`, started by ourfos-api as it starts the rest, so ourfos-api still writes only through
  workflows and never emails (ADR 9 holds). Its side effects come first: a requisition's reversal, then the reply in
  its thread, and only then the record. One that fails leaves nothing recorded, and the page says why
- Kept on `actions/{execution}` under the submission, beside its runs, as what a person did rather than what a
  workflow did: who, what, their comment, files and when. History shows both, newest first. Approve and disapprove set
  the status, shown even on forms whose status isn't otherwise tracked; a comment leaves it
- Who, for now, in the policy: Mark as done and a requisition's Disapprove for whoever may reverse entries (directors,
  zsaruchera); Approve and Disapprove on loan approvals and write-offs for directors; Comment for everyone who can read
  them. Lekkai@ is kept out of deciding anything
- The page waits for the record, as it does for a correction: the action's execution says if it failed, and why
- Not taken: **recording first and emailing after.** A record of something nobody was told is the worse failure. Nor
  ourfos-api asking the services to email: a second route, and a write, through the caller check

Changed: Mark as done is replaced by Post journal entry (ADR 19), and Disapprove by Close, to become Void (ADR 20).

### 17. A dialog that changes something is left only by its own buttons

- Correct, Reverse, every action, and the form's discard and submit: no ×, and neither a click outside nor Escape
  closes them, so a slip loses nothing and does nothing. Cancel is said on purpose
- They say what's in the way when you try, beside what's missing: a comment or reason, an account, debits that don't
  balance, or corrected lines still the entry's own. A reason alone corrects nothing
- Weightier ones become steps, with a review before anything is sent: #53

### 18. Corrections go live

- Ten corrections on dev, each post on a connection of its own (ADR 14), all landed in 10–14s with no uncertain post,
  so Correct journal entry is for everyone who may edit entries, and Enable corrections is retired
- Correct and Reverse journal entry are done on the requisition, from its top row with the other actions, rather
  than on the entry. Every action button there is outline, in its own color; only the dialog's own confirm is solid,
  so the step that sends something is the one that looks weighty

### 19. Post journal entry, where nothing is live

- Replaces Mark as done, which only said someone had dealt with it elsewhere. Shown on a requisition with no live
  entry: handed over the first time, or left reversed with nothing posted after (#893). The server refuses one that
  has a live entry, so a stale page can't post twice
- The correction's dialog, sharing its lines editor, with no lines to start from: one empty debit and one empty
  credit. Reference, transaction date and Mifos comments are filled in as Lekkai would have posted them, from the
  requisition (its reference number or response number, its disbursed date, its subject and response number), and
  shown so they can be checked and changed. Only what the requisition lacks is asked for. No reason is asked: a
  handover isn't the poster's fault. The run's id is added to the comments when it posts, as Lekkai's are
- The correction workflow posts it, without the reversal: the same fresh connection, the reply in the thread, the
  live entry set and the requisition done. A test requisition's goes to demo, as its first post would have. Who:
  whoever may edit entries, as for corrections
- Mark as done's records stay in History, still labelled as they were
- Disapprove is renamed Close here already, everywhere and in the store (kind `close`, status `closed`, permission
  `forms:<form>:close`), since it was only ever used on dev; who may close is unchanged until follow-up 5

### 20. Void, Comment for anyone, and every email's available next steps (planned: follow-up 5)

Decided here so it isn't lost; built in phase 15's fifth follow-up.

- **Void replaces Disapprove and Close**, everywhere and in the store: kind `void`, status `voided`, permission
  `forms:<form>:void`, labelled in full ("Void requisition"). It's for whatever is disapproved, a mistake or a
  duplicate: the record and its books are kept, as voiding does in accounting, never deleted. Close, renamed from
  Disapprove in follow-up 4, was only ever used on dev and stays unannounced until then; dev's closed and disapproved
  records keep their labels and aren't migrated. Prod has no actions of any kind as of 0.58.0. Voiding a requisition
  reverses its live entry first, so Reverse journal entry goes
- **Who:** Comment for anyone who can read the record, every form, requisitions included; the API checks nothing
  more. Void for anyone who can read it too, so someone can void one on a submitter's behalf, except a requisition
  with a live entry: voiding that reverses it in Mifos, so only accountants and directors may. Approve on loan
  approvals and write-offs for directors
- **Approve doesn't move the status:** it's recorded and shown, and the record stays received. Some approvals need one
  director and some two; that rule is #57. The same director can't approve twice
- **Available next steps** end every email in a thread, under a short rule (about 120px, `---` in plain text), not one
  across the page. By role, each action linked; actions anyone can take share an Anyone row, not repeated per role:
  - Requisitions: Accountant and Directors: Correct journal entry (Post journal entry when nothing is live) | Void
    when a live entry would be reversed. Anyone: Comment | Void
  - Loan approvals and write-offs: Directors: Approve. Anyone: Comment | Void
  - The note under them, for example: "Use the links above to correct, comment on or void this requisition in Ourfos
    instead of replying in Gmail. Ourfos will send the email notifications for you." Its verbs are those listed
- **One function decides what's available**, from the form, the record's state and the features on: the footer, the
  top-row buttons and the API's checks all use it, so an email never offers what the page or the API would refuse. A
  voided record lists none
- **A link opens its dialog:** `?action=<kind>` on the record's page opens that dialog once the record loads, IAP's
  sign-in keeping the URL. Cancel or a send takes the param off by replacing history, so a refresh or Back doesn't
  reopen it. One no longer possible, or not yours, opens nothing and says so, leading with what was tried: "You
  can't void this: this requisition is already voided"
- **Smaller things:** the record's breadcrumb gets a line of its own above its actions, so a long title never squeezes
  them. A void that reverses a live entry is one item in History, the reversal under it, not a second item titled as
  a correction

### 21. Backend features, per environment, in Terraform (planned: follow-up 5)

- A feature with server-side parts is switched per environment in Terraform: a `features` map in each environment's
  variables, handed to ourfos-api and ourfos-services as `FEATURES`, since ourfos-services sends the emails that list
  next steps. Changing one is a PR and a Cloud Build apply, reviewed and on record. The API refuses an action whose
  feature is off; the footer and the buttons leave it out
- ourfos-api serves them at `/api/features`; the front end loads them into the same OpenFeature flags, read-only.
  Browser switches (ADR 15) stay for front-end-only ones: tests in lists, test submissions
- `approvals` is the first, moving from the browser: Approve, Comment, Void and the footer. On on dev, off on prod
  until prod's variables say otherwise. Post and Correct journal entry aren't behind it
- Not taken: a Firestore config doc, which flips without a deploy but needs a screen and a history of its own; a flag
  service, too much for a handful. OpenFeature leaves the way open to one
