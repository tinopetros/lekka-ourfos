# Phase 4: add firestore db

## Goal

- One workflow, one service: `requisition` only calls `/requisitions/*`, and that service calls Mifos, Gmail and expenser for it
- The requisition service owns the requisition's state in Firestore: saved on arrival, a status as it moves, how the execution ended
- The workflow carries ids and what it branches on. The document carries the data
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
| notify | `POST …/notify` | simulate | classification, thread | |
| post | `POST …/post` | simulate | classification | transaction_id, `posted` |
| read_back | `GET …/read-back` | simulate | transaction_id | |
| confirm | `POST …/confirm` | simulate | thread, transaction_id | |
| handover | `POST …/handover` | thread_id, error, simulate | | |
| complete | `POST …/complete` | status, reason, transaction_id | | final status, execution |

- `{id}` is the execution id. `post` sends it to Mifos as the reference, as now
- `classify` still returns the classification, since `check`, `rejected` and `verify` branch on it
- `thread` takes `response_number` and `handover` takes `thread_id` in the call, so the handover path works even when the database doesn't

## The document

```
requisitions/{execution_id}
  requisition       as received
  response_number
  simulate          so a fixture's document says it was one
  status            received → classified → posted → done | rejected | handed_over | failed
  classification    { approve, reason, debit, credit, by }
  thread_id
  transaction_id
  reason            when rejected, handed over or failed
  execution         { id, revision, started_at, completed_at }
  updated_at
```

- Every write is a merge, never an append, so the workflow's retries are harmless
- A happy run: about five writes and four reads

## Writes and side effects

- Before anything leaves the building (receive, classify), a failed write fails the step, and the workflow retries or hands over as usual
- After Mifos or Gmail did something (post), a failed write is logged, not raised. The entry is in the ledger either way, and `complete` writes the transaction id again
- `complete` never turns a finished run red. If it can't write, it logs and the execution still returns its result

## Config

```bash
# Cloud Run env, set by Terraform
FIRESTORE_DATABASE=ourfos
```

- `google-cloud-firestore`'s async client, one per instance

## Terraform

- Just the env above. Infra owns the database, its rules, and now every project role our accounts hold, `datastore.user` included ([infra#12](https://github.com/tinopetros/lekka-ourfos-infra/pull/12))
- Our three project grants become `removed` blocks, so our state forgets them without revoking them. They go once dev and prod have both applied
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

**2. Ours loses project IAM**, once dev and prod have both applied `removed.tf`. Until then a prod plan still reads those grants:

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  gcloud projects remove-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin --all
done
```

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
