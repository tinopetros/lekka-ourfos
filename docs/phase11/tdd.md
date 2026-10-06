# Phase 11: we post to Mifos

## Goal

- A requisition's approved lines are posted to Mifos as a journal entry, read back, and confirmed in a last email: what Mifos has, and its transaction id
- Done well on dev first, against Mifos's `demo` tenant. Prod is wired, `default` tenant, but not released until we say so
- Everything up to `post` is phase 10's, unchanged

## Shape

```
expense ─▶ … ─▶ suggest ─▶ post ─▶ read back ─▶ verify ─▶ confirm
                             │          │                    └─ the last email: the lines Mifos has, and its id
                             │          └─ GET /journalentries?transactionId=
                             └─ POST /journalentries, the run's id as its reference
```

- The same steps and paths as phase 5's stub: only `integrations/mifos.py` and `confirm` change for real
- `mifos.py` is a thin layer over [`mifos-connector`](https://github.com/tinopetros/mifos-connector-py), our own client, pinned to a release tag

## The dependency (ADR 1)

- `services/pyproject.toml`: `mifos-connector @ git+ssh://git@github.com/tinopetros/mifos-connector-py.git@0.0.0`, so `uv.lock` holds its commit
- The repo is private, so whatever installs it needs read access to it:

  | Where                        | How                                                                                                       |
  | ---------------------------- | --------------------------------------------------------------------------------------------------------- |
  | My machine                   | my SSH key, as for any repo of mine                                                                       |
  | GitHub Actions, `make check` | the `MIFOS_CONNECTOR_TOKEN` repo secret, a read-only fine-grained PAT, swapped in for `ssh://` by git     |
  | Cloud Build, both triggers   | the same PAT, as the `mifos-connector-token` secret in `ourfos-prod`, given to the `package` step only    |
  | The image                    | nothing: `package` builds the connector's wheel, and the Dockerfile installs it from the staged directory |

- The token never enters the image or the Docker build, and the deployer only reads it, never writes it
- The PAT and both secrets are made by hand: infra's README, bootstrap 12

## Mifos's settings (ADR 2)

| Env var            | Dev                        | Prod                    | From                         |
| ------------------ | -------------------------- | ----------------------- | ---------------------------- |
| `MIFOS_BASE_URL`   | the Mifos server's API URL | the same                | `terraform/env/<env>.tfvars` |
| `MIFOS_TENANT_ID`  | `demo`                     | `default`               | tfvars                       |
| `MIFOS_OFFICE_ID`  | `1`                        | `1`                     | tfvars                       |
| `MIFOS_CURRENCY`   | `USD`                      | `USD`                   | tfvars                       |
| `MIFOS_VERIFY_SSL` | `false`, for now (ADR 7)   | `true`                  | tfvars                       |
| `MIFOS_USERNAME`   | a `demo` tenant user       | a `default` tenant user | secret `mifos-username`      |
| `MIFOS_PASSWORD`   | its password               | its password            | secret `mifos-password`      |

- The secrets are per project, made by hand like `trigger-token`, so neither reaches Terraform's state (infra bootstrap 13)
- `default` is production Mifos. Dev can't reach it three ways over (ADR 3):
  - dev's secret is a `demo` user, which `default` doesn't know
  - `variables.tf` refuses `mifos.tenant_id = "default"` for any project but `ourfos-prod`
  - `mifos.py` refuses it too, before it sends anything, unless `GOOGLE_CLOUD_PROJECT` is `ourfos-prod`
- `demo`'s chart is `default`'s: all 52 of `accounts.csv`'s accounts have the same GL id, code and name there (checked 2026-10-06). So expenser's lines post to `demo` as they would to the books

## Post

`POST /journalentries`, as the stub's arguments:

| Field               | Value                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------- |
| `officeId`          | `MIFOS_OFFICE_ID`                                                                     |
| `currencyCode`      | `MIFOS_CURRENCY`                                                                      |
| `transactionDate`   | the requisition's `disbursed_on`, or the day it's posted, in Harare, when it has none |
| `referenceNumber`   | the run's id, as today: what a handover tells a person to look up                     |
| `comments`          | the email's subject, `Requisition Approval Request Form - {payable_to} - #{n}`        |
| `debits`, `credits` | `{glAccountId: glId, amount}` per classified line                                     |

- Returns `{transactionId}`: the run keeps it as `mifos_transaction_id`, status `posted`, as today. A run that already has one returns it and posts nothing
- **Never retried blind** (phase 1). One client per instance, with a 15s timeout under `call_service`'s 20s, so a slow Mifos is ours to call uncertain:

  | Mifos                        | The service answers  | The workflow                                             |
  | ---------------------------- | -------------------- | -------------------------------------------------------- |
  | a 4xx, e.g. a closed account | 422, Mifos's message | hands over: nothing was posted                           |
  | never reached                | 503                  | hands over: nothing was posted                           |
  | a 5xx, or timed out          | 504                  | hands over as `PostUncertain`: check the reference first |

  Only what certainly didn't land says so. A 5xx may have come after the write

- A **test run never posts** (closes release 1 ADR 3's revisit). `post` returns `{"skipped": "test"}`, read back and verify are skipped, and the last email says it wasn't posted

## Read back and verify (ADR 4)

- `GET /journalentries?transactionId=`: what Mifos has, not what we sent
- The service compares line by line, not by count: each `glId`, side and amount we posted is there once, and nothing else is. It answers what differs as `mismatch`, and `verify` hands that over as `Unconfirmed`, naming the transaction
- A stub's transaction, `stub-txn-…`, is read back from the stub, so a stubbed post never reads Mifos
- The read-back is kept on the run as `posted`, the lines the last email shows

## The last email (ADR 5)

Closes phase 9 ADR 6, and phase 1 ADR 2: once a post is confirmed, the confirmation is the word that counts.

- A reply in the thread, from Lekkai: **Posted to Mifos as transaction {id}.**
- The table: Account, GL Code, Debit, Credit, from the read-back, with a total row. Same table style as the suggestion's
- The reference, the run's id
- A test run: **Not posted: this was a test run.**, and the suggestion's lines, so the email still shows what would have been
- `emails.confirmation` on the run, so a retried `confirm` doesn't send twice (phase 9 ADR 7)
- Sender's name: Lekkai

## Fixtures and smoke

- Any `simulate.mifos_post`, `"stub"` among them, keeps the canned answer, on dev only, like every simulate. So the failure fixtures, `post-503`, `post-timeout`, `post-unrecorded` and `read-back-mismatch`, never reach Mifos
- `happy` posts to `demo` for real, on every dev build: an entry a merge. `happy-gcs` and `google-doc` stub their post
- `done` returns the `mifos_transaction_id`, and smoke's `happy` checks it isn't `stub-txn-…`

## Bootstrapped, once

In infra's README:

- **12.** A fine-grained PAT, read-only on `tinopetros/mifos-connector-py`: as `mifos-connector-token` in `ourfos-prod`'s Secret Manager, readable by `ourfos-app-deployer@`, and as `MIFOS_CONNECTOR_TOKEN` in lekka-ourfos's Actions secrets
- **13.** Per project, `mifos-username` and `mifos-password`, readable by `ourfos-services@`. Dev: the `demo` user. Prod: a `default` user that can only make journal entries, made when we're ready to release

## Done when

- `uv sync` installs the connector on my machine, in Actions, and in the dev image
- On dev, a `demo` post from the image answers: the services log the transaction id
- `make test` covers the post's fields, each Mifos failure's status, verify's mismatches, the tenant guard, and the last email
- On dev, smoke passes, `happy` posted to `demo` and confirmed in its thread
- A manual requisition on dev ends with the last email, and the entry is in `demo`
- Prod's plan in the dev build shows its Mifos env and secrets, and nothing is released

## Not in this phase

- Releasing to prod, and prod's Mifos user
- Looking up a timed-out post by its reference before handing over (README TODO). Fineract can't filter journal entries by reference
- The write-off form posting its write-off
