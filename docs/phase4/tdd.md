# Phase 4: add firestore db

## Goal

- One workflow, one service: `requisition` only calls `/requisitions/*`, and that service calls Mifos, Gmail and expenser for it
- The requisition service owns the requisition's state in Firestore: saved on arrival, a status as it moves, how the execution ended
- The workflow carries ids (execution, thread, transaction) and what it branches on. The document carries the data
- Dev only. Nothing gets tagged into prod this phase

## Shape

```
workflow ─▶ ourfos-services /requisitions/{execution_id}/…
              │
              ├─ receive · classify · thread · notify · post · read-back · confirm · handover · complete
              │
              ├─ expenser    in process, as in phase 3
              ├─ mifos       a module now, not a router
              ├─ workspace   a module now, not a router
              └─ store       Firestore, database ourfos, collection requisitions
```

- `mifos` and `workspace` are plain modules the requisitions router calls. Same container, so no HTTP hop to ourselves
- They're written as if they were remote: JSON-shaped dicts in and out, failures as HTTP statuses. Going networked later means swapping a module's insides for an authenticated `httpx` call; its callers and the workflow don't change
- The workflow keeps its logic: retries, `check`, `verify`, `PostUncertain`, handover. Only the paths and bodies change, plus `receive` first and `complete` last

## Paths

| Step | Call | Body / query | Reads | Writes |
| --- | --- | --- | --- | --- |
| receive | `POST /requisitions/{id}` | requisition, simulate | | the document, `received` |
| classify | `POST …/classify` | simulate | requisition | classification, `classified` |
| get_thread | `GET …/thread` | response_number, simulate | | `thread_id` |
| notify | `POST …/notify` | thread_id, simulate | classification | `emails.classification` |
| post | `POST …/post` | simulate | classification | transaction_id, `posted` |
| read_back | `GET …/read-back/{transaction_id}` | simulate | | |
| confirm | `POST …/confirm` | thread_id, transaction_id, simulate | | `emails.confirmation` |
| handover | `POST …/handover` | thread_id, error, simulate | | `emails.handover`, if it can |
| complete | `POST …/complete` | status, reason, transaction_id | | final status, execution |

- `{id}` is the execution id. `post` sends it to Mifos as the reference, as now
- `classify` still returns the classification, since `check`, `rejected` and `verify` branch on it
- Ids come from the workflow, never the document: a write after a side effect may not have landed (see below)
- `thread` and `handover` need nothing from the database, so the handover path works even when the database doesn't
- `complete` runs however the run ends, `failed` included, and never fails it

## The document

```
requisitions/{execution_id}
  requisition       as received
  response_number
  simulate          dev only, so a fixture's document says it was one
  status            received → classified → posted → done | rejected | handed_over | failed
  classification    { approve, reason, debit, credit }
  thread_id
  transaction_id
  reason            when rejected, handed over or failed
  emails            { classification | confirmation | handover: { message_id, at } }
  execution         { id, revision, started_at, completed_at }
  updated_at
```

- Every write is a merge, never an append, so the workflow's retries are harmless
- Status writes go through a transaction: once it says `done`, `rejected`, `handed_over` or `failed`, a late step's fields still land but its status doesn't
- Status is the headline. `emails` says which emails went out and when, so a UI needs one read, not a trip to Gmail. The thread is still one click away through `thread_id`
- A happy run: about seven writes and four reads

## Writes and side effects

- Before anything leaves the building (receive, classify), a failed write fails the step: 429 and 503 are retried, anything else hands over
- After Mifos or Gmail did something (post, and every email), a failed write is logged, not raised. So is `thread_id`, which handover needs without the database. The entry is in the ledger either way, and `complete` writes the transaction id again
- `complete` never turns a finished run red. If it can't write, it logs and the execution still returns its result

## Config

```bash
# Cloud Run env, set by Terraform
FIRESTORE_DATABASE=ourfos
# The workflow's env: on in dev.tfvars, off everywhere else
SIMULATE=on
```

- With `SIMULATE=off` the workflow ignores `simulate` from the trigger, so nothing downstream sees it and prod never stores it

- `google-cloud-firestore`'s sync client, one per instance. The routes are sync, so FastAPI runs them in threads

## Terraform

- Just the env above. Infra owns the database (Firestore API and realtime updates on), its rules, and now every project role our accounts hold, `datastore.user` included ([infra#12](https://github.com/tinopetros/lekka-ourfos-infra/pull/12))
- Our three project grants leave our state without being revoked: `removed` blocks while the PR is open, `terraform state rm` at merge
- What stays here is who may call our own resources: `run.invoker` on `ourfos-services` and the trigger
- No indexes: every read is by id

## Fixtures and smoke

| Fixture | simulate | Ends | Document |
| --- | --- | --- | --- |
| every phase 1–3 fixture | as before | as before | the matching status |
| `post-unrecorded` | `mifos_post: unrecorded` | `done` | `done`, with the transaction id |

- `unrecorded` posts, then fails the write that follows. Proves a ledger entry is never handed over just because we couldn't write it down
- Smoke is unchanged. A missing grant or wrong database name fails `receive`, which hands over instead of `done`, so smoke still catches it

## Testing by hand

```bash
make deploy
make run FIXTURE=happy
make doc ID=<execution_id>    # the document, straight from the Firestore REST API
```

## Bootstrapped, once

The deployer stops granting project roles. In order, from a shell logged in as a project owner:

**1. Infra's deployer may grant our roles**, before infra#12 merges:

```bash
SA=deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  gcloud projects remove-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin --all
  gcloud projects add-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin \
    --condition='^;^expression=api.getAttribute("iam.googleapis.com/modifiedGrantsByRole", []).hasOnly(["roles/cloudbuild.builds.builder", "roles/datastore.user", "roles/datastore.viewer", "roles/logging.logWriter", "roles/workflows.invoker", "roles/aiplatform.user", "roles/modelarmor.user"]);title=deployer-grantable-roles'
done
```

**2. At merge**, once infra owns the grants in both projects, in order:

- `terraform state rm` the three grants, in dev and prod
- Drop `removed.tf`, merge
- Our deployer loses `projectIamAdmin`, in both projects

Nothing else merges to main in between: its dev apply would put the grants back in our state, and this merge would then revoke them.

## Done when

- Every fixture ends exactly as before on dev, and `make doc` shows the matching final status
- `post-unrecorded` ends `done`, and its document has the transaction id
- Smoke passes on the dev build after merge
- Infra grants our project roles, and our plan shows the three grants forgotten, not destroyed

## Not in this phase

- Prod
- A re-run that skips what already happened (phase 1 ADR 6)
- Saving in the trigger
- A TTL on dev documents
- Networked services
