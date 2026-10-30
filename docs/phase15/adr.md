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

### 9. Corrections from the UI, beside reversals

- Two buttons on a live entry, each with a tooltip: Reverse journal entry posts its mirror and leaves nothing live;
  Correct journal entry posts its mirror and then the lines it's given. Both need `journal_entries:edit`, and both
  start the correction workflow, as phase 12 built it: no lines reverses, lines correct
- The dialog starts from the live entry's lines. Each line picks its account and amount, lines can be added and
  removed, and it submits only when debits equal credits. The API checks the same, and refuses an account that
  isn't postable in the entry's tenant
- Accounts are Mifos's own, read through mifos-connector 0.1.0's `gl_accounts` and `postable` (DETAIL, enabled,
  manual entries allowed). Partly #<issue>: the picker reads live accounts, expenser still reads its CSV
- ourfos-services reads them, not ourfos-api: the API keeps no Mifos credentials, so it still can't post. The API
  calls the services with its own identity, which Terraform lets invoke them
- Kept 10 minutes per tenant, so a new account shows soon after it's made. A failed read falls back to the last
  good one, and to an error only when there's none
