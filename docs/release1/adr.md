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
- **Changed** by [phase 15 ADRs 11 and 12](../phase15/adr.md): a week, not a day, and billed to ourfos-api's own project
