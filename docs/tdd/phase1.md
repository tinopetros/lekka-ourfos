# Phase 1: the whole workflow, stubbed

## Goal

- Stand up the full requisition flow from the README end to end, with every service a stub
- The workflow is the star of this phase: real steps, real auth, real error handling. The services just log and say "got it"
- Built with what I learnt in [hello-gcp-workflows](https://github.com/tinopetros/hello-gcp-workflows), nothing fancier

## Shape

```
curl ─▶ trigger (Cloud Run Function, public)
          │  starts an execution, logs and returns its id
          ▼
        requisition workflow
          ├─ classify   POST /requisitions/classify
          ├─ check      in the workflow: approved & debits == credits? OR not approved & reason
          ├─ get_thread GET  /workspace/gmail/thread/   (get the thread id, i.e while Forms is still handling initial notification email)
          ├─ notify     POST /workspace/gmail/notify/thread/{id}        (interim: share the classification)
          ├─ post       POST /mifos/journal-entries
          │             GET  /mifos/journal-entries/{id}   (read it back)
          ├─ handover   POST /workspace/gmail/notify/thread/{id}        (if anything failed, send the reason)
          └─ confirm    POST /workspace/gmail/notify/thread/{id}        (final email)
                        │
                        ▼
                ourfos-services (one FastAPI Cloud Run, private)
                  requisitions.py · mifos.py · workspace.py - and their dependencies
```

- One service with a file per area, so any of them can be pulled out into its own service later without a rewrite
- Stubs log the request (with the execution id) and return a canned acknowledgement
- Stubs also take a `simulate` field from the fixture e.g. `{"simulate": {"mifos_post": 503}}` so every error path can be forced on purpose instead of waited for
- One notify endpoint for everything: its body carries either a `classification`, an `error` (the handover reason) or a `confirmation`, and it renders whichever it gets

## Error handling

- One subworkflow, `call_service`, wraps every HTTP call: OIDC auth, a timeout, the execution id as a header, and the retry policy
- Retry 429, 5xx and connection errors with backoff. Never retry a 4xx, the request is wrong not the network
- **Posting to Mifos never retries on a timeout.** It may have landed, and a blind retry is how one requisition becomes two journal entries. Only a failed connection (never got there) is retried
- `check` failing is not an error, it's an outcome: hand over with the reason
- Every failure ends up in one `handover` path that calls notify with `{"error": "reason"}`. No failure path ends silently
- `get_thread` finding nothing is an exception, not a handover: until we send the first email ourselves, Forms' notification should always be there
  - First it retries with a long backoff (a few minutes, `sys.sleep` is free) in case the email is just late
  - Still nothing? Raise, and the execution fails red. No email, since there is no thread to send it to
  - Workflows cannot resume a failed execution, so "resume" means re-running with the same input once it's fixed. That is safe because nothing irreversible has happened before this step
- If the handover email itself fails, log at ERROR and let the execution fail, so it shows up red in the console

## Access

- `trigger` is unauthenticated, for now. A shared key/phrase is the obvious next step and probably 20 minutes of work
- Every deployable that actually needs one gets its own service account:
  - `trigger` can only start workflow executions (`roles/workflows.invoker`)
  - the workflow can only invoke `ourfos-services` (`roles/run.invoker` on that one service) and write logs
  - `ourfos-services` gets nothing yet
- `ourfos-services` is private for now, only the workflow can call it

## Observability

- Every log line carries the workflow execution id, so one filing can be followed from trigger to final email in Cloud Logging
- Workflow deployed with detailed execution history so each step's inputs and outputs are visible (to confirm the flag while building)
- The trigger returns the execution id so I can go straight to it

## Layout

```
functions/trigger/                  the public entry point
  main.py · pyproject.toml · uv.lock
services/                           FastAPI app, one router per area
  main.py · pyproject.toml · uv.lock · Dockerfile
  routers/requisitions.py · mifos.py · workspace.py
workflows/
  requisition.workflows.yaml        .workflows.yaml for free validation in VS Code
  fixtures/*.json                   happy path + one per forced failure
terraform/                          one root for everything in this repo, state in gs://ourfos-dev-tfstate/ourfos
Makefile                            sits on top of terraform, like hello-agent-deployment/tf-adk
```

## How I will build it

1. Deploy each piece by hand with `gcloud` to `ourfos-dev` (`africa-south1`), run every fixture, read the executions
2. Tear all of it down, so Terraform starts from a clean project and nothing hand-made lingers
3. Terraform owns everything in this repo: service accounts, IAM, the function, the Cloud Run service and the workflow. APIs are infra's: I enable what I need by hand while building, and flag anything infra's list is missing
4. A Makefile on top of Terraform for my own manual testing: `package`, `copy-to-cloudshell`, `tf-init/plan/apply/destroy/output`, plus `run` with a fixture
   - `make deploy` = Cloud Build builds the service image (tagged with a hash of the source) and then `terraform apply` points Cloud Run at it. Terraform never builds anything itself, it just takes the image as a variable
   - The same build-then-apply is what prod lines up with later

## Testing it by hand

- From here: `make deploy`, or `make copy` then `make deploy` in Cloud Shell. Terraform shows the plan and waits for a `yes`
- `make run` for the happy path, or `make run FIXTURE=classify-503` for one that retries and hands over
- Each run prints an execution id: `make logs ID=<id>` tells its whole story

## Python

- `uv` for everything, so a venv is one `uv sync` away
- Cloud Run and Cloud Functions still want a `requirements.txt`, so it is generated from `uv.lock` with `uv export` at package time and never committed. One source of truth, and the deploy gets what it expects

## Done when

- `curl` with the happy-path fixture returns an execution id, and that execution succeeds through every step
- A missing thread fails the execution red after its retries, and a re-run with the same input then succeeds
- Every other forced failure lands in `handover` with a sensible reason, and a 4xx is visibly not retried while a 503 visibly is
- A Mifos post timeout does not post twice
- Filtering Cloud Logging by one execution id shows the whole story

## Not in this phase

- Real classification, Gmail, Drive or Mifos
- Firestore, callbacks, prod
- The key on `trigger` (next, if quick)

## Artifact Registry

- Registries belong to infra. Terraform here only looks one up (a `data` source for `ourfos` in `africa-south1`) and never creates it, so `plan` fails until infra has made it. That failure is the reminder
- While building by hand, I'll create that repo myself with `gcloud`, and delete it in the teardown (step 2)
