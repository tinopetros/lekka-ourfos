# Phase 1: decisions and shortcuts

What we chose in phase 1 and, mostly, what we knowingly left temporary. When a later phase deals with one, it says so in its own ADR and links back here.

### 1. `get_thread` + notify reply on the Forms thread

- Google Forms sends the first email, so we have to go looking for its thread before we can reply into it
- That is a search, a read scope on Gmail, and a whole failure mode (the thread missing) that only exists because we don't own the first email
- **Revisit when** we send the acknowledgement ourselves: keep the thread id at the start, drop `get_thread`, and collapse all the notify calls onto a thread we already know
- **Closed** by [phase 9 ADR 1](../phase9/adr.md)

### 2. Notify shares the classification in the meantime

- Mifos posting will take a while to get right, so notify sends the classification on its own, to be useful before anything is posted
- **Revisit when** posting to Mifos is real and trusted: notify becomes the final confirmation only

### 3. Classify lives in `ourfos-services`

- The agent starts on our own runtime, not in `lekka-ourfos-agents`
- **Revisit when** it moves to the agents repo (more on that later)

### 4. One Cloud Run for every service

- `requisitions`, `mifos` and `workspace` are separate files in one FastAPI app, sharing one service account
- **Revisit when** any of them needs its own credentials (Gmail delegation and Mifos credentials should never share an identity) or its own scaling

### 5. `trigger` is unauthenticated

- Anyone with the URL can start an execution. Fine for stubs and curl
- **Revisit** next: a shared key/phrase, before anything real is behind it

### 6. No database, so "resume" means re-run

- Workflows cannot resume a failed execution, and there is nothing of ours recording progress
- Safe for now because every step before `post` can be repeated without harm
- **Revisit when** there is a DB: record progress and make a re-run skip what already happened, especially `post`

### 7. Artifact Registry belongs to infra

- Terraform here only looks up an `ourfos` repository and fails if it is missing
- The one used for the manual build is made by hand and deleted in the teardown
- **Revisit when** infra creates it (Terraform here fails until it does)

### 8. `trigger` can start any workflow in the project

- Workflows only grants `roles/workflows.invoker` at project level, and Terraform has no per-workflow IAM either
- An IAM condition on the workflow name might work, but it's undocumented and Terraform wouldn't know whether it's actually enforced
- Accepted for good. The trigger only ever starts the workflow named in its `WORKFLOW` env var, which Terraform sets
