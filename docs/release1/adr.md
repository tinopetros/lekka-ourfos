# Release 1: decisions

Phases 1 to 9 and what follows them are release 1. Each phase kept its own ADR; the meaningful ones get gathered here later. New decisions that belong to no phase start here.

### 1. The services run on one instance (latency study 1)

- A run's calls to the services come one after another. On dev, Cloud Run started a second instance for `acknowledge` while the one `receive` had woken sat idle: about 6s of extra cold start
- So `max_instance_count = 1`. The first cold start from zero stays: keeping an instance warm is billed by the hour, for a few requisitions a month
- At most 10 requests at once on it (`max_instance_request_concurrency`), about 10 runs mid-step. A classify holds its files about three times over, so a burst can't pile enough onto the one instance to run it out of memory. The eleventh waits, or gets a 429 the workflow retries
- The trigger keeps Cloud Functions' default, 77 instances in `africa-south1`, one request each. It's public, but a flood costs little, and a cap risks refusing a real submission the form's add-on may not retry
- **Revisit** if volume grows: a second instance, or 2 GiB, before any run waits on the limit
- **Closed** in part by phase 15 ADR 7: the trigger is retired, so only the services' limit is left

### 2. Drive files in one call each, all at once (latency study 1)

- Drive took 7–11s for `happy`'s two files (4.8 MB) on a warm instance, and 24s on a cold one. GCS took 0.3–0.5s for `happy-gcs`'s. Nobody waits on a run, but at that rate a file near the 40 MB cap would take about 80s: close to classify's 120s timeout
- One call a file: the bytes straight away, with Drive's own content type. Only a Google Doc, Sheet or Slides, which Drive refuses to download, is exported as PDF, on a second call
- Every file at once: a requisition takes as long as its slowest file, not their sum. Threads share the cached sessions, so a cold instance may sign a token twice, harmlessly
- Each file's time is logged, so the next change is measured
- **Revisit** with the front end: copy each Drive file into the bucket once, on receipt, so classify only ever reads GCS

### 3. A test run tells only lekkai@, and its submitter if listed

- `?test=true` beside `?workflow=`, on dev and prod alike. The run is real: cleaned, classified by the model, stored. Only who hears changes
- Its emails go to `lekkai@`, never the project's list, and their subjects start `[TEST]`, so a forwarded one can't pass for real
- The submitter too, only if `test_to` in `terraform/env/<env>.tfvars` lists them: `tpetros@` for now. Everyone else tests on dev, not with the flag
- The document keeps `test: true`, so anything that lists requisitions can leave them out by default
- `true` or `false` only: anything else is a 400, as the cleaner guesses nothing
- The token still guards the trigger, so only whoever holds it can make a run a test
- Not `simulate`: that forces failures, on dev only. A test run fails only as a real one would

**Closed** by phase 14 ADR 9: who may send a test is a permission now, so a test also tells its submitter, whoever they are. `test_to` is gone
- **Revisit** with Mifos: a test run must never post. Until then `post` is a stub, and a test run goes through it like any other
- **Closed** by phase 15 ADR 8: a test run posts, to `demo`, on dev and prod alike
  - **Closed** by [phase 11](../phase11/tdd.md): a test run never posts, and its last email says so

### 4. Permissions stay in code, for now

- Who may do what is `POLICY` and `EXCLUDE` in `services/api/permissions.py`. The permission names belong to the routes that check them, so the two change together, in one PR
- pytest checks the real policy: that `lekkai@` reads no journal entries is proven in CI, not just in a sample
- Moving it to Terraform would let dev and prod differ, and change access without a rebuild. But it splits the rules from the code they guard, turns typos into runtime errors, and still takes a PR and a deploy. With this few people, a rebuild isn't the bottleneck
- If dev and prod ever need different people, only the email lists would come from tfvars, as `POST_TO_MIFOS` does. The grants and exclusions stay in code, under test
- **Revisit** with an admin page: in the long run, who has what belongs in the database, editable by ourfos admins, not in code or Terraform. Terraform would be a detour on the way there

### 5. People by name, from Workspace's directory

- All IAP tells us is an email. Names, photos, titles and managers are in Workspace's directory, by email: the Admin SDK's `users.get`, read-only scope `admin.directory.user.readonly`. That covers anyone at lekkacredit.com, submitters too, not just whoever is signed in
- `ourfos-api@` reads it as itself, through **ourfos user reader**, a custom admin role: Users → Read only. As it reads groups as **Groups Reader** (phase 14 ADR). No domain-wide delegation, no prompt for anyone. Both roles, and how to assign them, are in lekka-ourfos-infra's README (tinopetros/lekka-ourfos-infra#24, which also enables `admin.googleapis.com`)
- A name is kept on `users/{email}` and asked for again after a day. Never deleted: when the directory can't say, the name last saved stands, and without one, the email. Each instance keeps it 5 minutes too, so a page of submissions isn't a read a row
- The UI shows people by name, dotted like a time. Held over: their name, their email, and a copy of the email. "Hi" takes the first word of the name
- Only lekkacredit.com addresses are looked up: the directory knows nobody else
- Not signing in with the profile scope: a second sign-in beside IAP, and it only ever knows who's signed in
- **Revisit** with the admin page: a name someone picks for themselves would go beside the directory's, not instead of it

### 6. Backfilling the Google Forms' responses

- Draft, on PR #48: written to dev as samples, not yet to prod. Responses only for now
- Sources:
  - Requisitions: [Requisition Approval Request Form (Responses)](https://docs.google.com/spreadsheets/d/1dk_bw9WBry0PA4FGnyGIYOkKT8M4_VLCrAvM54FQvzU/edit), #1–885, 17 Nov 2024 to 23 Oct 2026
  - Loan approvals: [Loan Approvals Tracker](https://docs.google.com/spreadsheets/d/1JmPMUbdTm8iquUCKF68YHG9TqrnpNPWvomMQvfaRRDU/edit), #1–641, 5 Aug 2024 to 27 Oct 2026
  - Vehicle logs: [Vehicle Log Form (Responses)](https://docs.google.com/spreadsheets/d/1VeYnFbeaSg91G3GKUlKB47_6q6AZLMJDuJhQxqawiNU/edit), #1–89, 7 Jan 2025 to 1 Oct 2026
  - Write-offs never had a Google Form. Three emails from Leon Tanga, numbered #1–3 by date:
    - #1 "Request for Loan Account Write-Off – Late Mr Mshawati", Gmail thread-f:1861083503068554811, 30 Mar 2026
    - #2 "REQUEST FOR WRITE-OFF – VIRGINIA CHIRAWA ACCOUNT", thread-f:1877133247418167221, 23 Sep 2026
    - #3 "REQUEST FOR WRITE-OFF – PANASHE KUREWA ACCOUNT", thread-f:1877133657395301900, 23 Sep 2026
- Each keeps its Google Form's response number, tests too, so prod's numbers stay unique: ourfos's own carry on past the highest (requisitions from 886; the others' first will be 642 and 90), and prod's tests are below zero. A row already on prod from the webhook is left as it is
  - The requisitions sheet's row 564 is empty and never took a number: without it, the sheet's numbers are prod's exactly
  - The loan sheet's rows 2 and 3 are empty but did take numbers: filled as tests
  - Write-offs go in before any real one from ourfos, which would otherwise take #1
- Stored as the webhook's were: no `source`, the Google Form's answers and keys, so the UI shows them as it shows those. Ids are `backfill-<form>-<number>`, since the sheets don't have the Form's response ids. Status `backfilled`. What the answers don't hold goes under `backfill`: the source, the sheet row, why it's a test, the sheet's other columns (requisitions' Posted and items, the loan sheet's Approval, Approver and comment), what was fixed and what's still off
- Timestamps are each sheet's own timezone, read off prod's matching rows: New York for requisitions and vehicle logs (prod's #885 is 7:15 in the sheet and 11:15 UTC), Harare for loan approvals (#641 is 11:45 and 09:45 UTC)
- A test is a row that says "test" or "testing" in its name, payee, purpose or comments, a driving test aside, and vehicle log #89's 898989 odometer. Requisitions the sheet marks duplicate are tests for now, to be rejected once there's such a state: #7, #8, #9, #369, #370
- Fixed:
  - Requisition amounts to what their comments confirm: #236 "One thousand two hundred and seventeen dollars(1217)" to 1217, #565 "3/13/1901" to 438 ($430 laptop, $8 mouse)
  - Vehicle logs: seven trips ending "AM" before they start, read as PM (#12, #17, #21, #30, #32, #34, #64); #3's end date 10/20/2025 to 1/20/2025; #26's start date 2/10/2025 to 3/10/2025
  - Write-offs' client and loan account numbers, from prod's Mifos and on each record, each loan matching its email's balance. Mshawati is spelt Mshawatu in Mifos, where his salvaged loan is already written off
- Left as they are:
  - Requisitions #1 and #2 have no signed requisition form, grandfathered: the UI shows their answers as kept
  - Vehicle logs' odometer readings that run backwards between trips, and distances that don't add up
  - Requisition #875 (Expenses, ¥5000, a $5000 transfer) reached prod but broke: no number or answers, status handed_over
  - Prod marks requisition #844 and loan approvals #628 and #629 as tests. #844 is a re-send of #843; the other two look real
- Gaps:
  - Vehicle logs: none from 20 Nov 2025 to 4 Feb 2026, and holes of over a month in Aug–Sep 2025, Mar–Apr 2026 and Apr–Jun 2026
  - Write-offs: their screenshots are in the emails, not in Drive. Chirawa's and Kurewa's are still open in Mifos
- Later: link each response to its email thread; link requisitions to the journal entries that look like theirs, and maybe expenser v1's suggestions; backfill journal entries from Mifos
