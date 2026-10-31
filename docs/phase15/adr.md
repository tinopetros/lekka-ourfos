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
  (`forms:<form>:test`, the journal by requisitions') can show them, with a toggle at the list's foot, as in the form.
  It's in the URL, so the way back and previous/next keep it
- Left out by the API, which reads on until a page is full: filtered in the UI, a page could come back empty
- An entry says it's a test from now on. One recorded before is a test if its submission is, read with its page
- A record opened by its link still shows, test or not
