# lekka-ourfos

Internal workflows for [Lekka Credit](https://lekkacredit.com), orchestrated
with Google Cloud Workflows.

A form is submitted, something reviews it, it gets filed, and somebody gets a
reply. This repo holds the orchestration — the workflow definitions, the
services those workflows call, and the apps that read the same records.

| Workflow  | Forms                                                 | What it does                                                        | Status |
| --------- | ----------------------------------------------------- | ------------------------------------------------------------------- | ------ |
| `expense` | requisition                                           | Requisition form → posted Mifos journal entry, one thread of emails | Design |
| `intake`  | vehicle log, loan approval request, write-off request | Received and acknowledged: stored, and the first email sent         | Design |

A submission is one document, keyed by the form's `response_id`, and every workflow run on it is a document under it: a later approval or reversal is a run of its own. See [phase 10](docs/phase10/tdd.md).

## The shape of it

```
Google Form ─▶ trigger ─▶ Workflows execution ─▶ one thread of emails, then done
                 │            │
                 │            ├─ receive     (every form)
                 │            ├─ acknowledge (every form: the first email, which starts the thread)
                 │            ├─ classify    (expense on: expenser, an ADK agent, in the services)
                 │            ├─ check       (deterministic, in the workflow)
                 │            ├─ suggest     (a reply: Lekkai's suggestion)
                 │            ├─ post        (Mifos, and read it back)
                 │            └─ confirm     (a reply: posted, once Mifos is real)
                 ▼
             Firestore
```

## Where things live

| Repo                                                                       | Owns                                                                                                |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| [`lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra)   | Project-level: APIs, service identities, the Firestore database, Artifact Registry, quotas, budgets |
| [`lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents) | Agents: Reasoning Engines, agent service accounts, Model Armor, prompts, evals                      |
| **`lekka-ourfos`**                                                         | Workflows, services, apps, Firestore indexes and rules, Cloud Build triggers                        |

## Layout

```
envs/dev|prod/     Terraform: service accounts, IAM, Firestore indexes, triggers
packages/          shared libraries, never deployed alone
services/          called BY workflows — invoker is the workflow's SA only
  classify/        a requisition's files, and expenser's call on them
  integrations/    third parties: Mifos, and Workspace as lekkai@
agents/            ADK agents, run inside services for now (expenser, behind Model Armor)
apps/              user-facing — behind IAP
workflows/         the definitions, their shared lib, and fixtures per form for running them
```

## Testing by hand

The Makefile is for manual testing on `ourfos-dev`, its default (`ENV=dev`). Each env has its own Terraform data dir, so `ENV=prod` can't plan against dev's state, but prod normally goes out by tag.

Fixtures are what a form's webhook posts, in `workflows/fixtures/<form>/`: every value a string, files as Drive links or `gs://` refs into the attachments bucket. The trigger cleans them into the form's model (`services/forms.py`) and answers 400 with every problem when it can't; `make test` covers the cleaners. A requisition is strictly typed; the other forms are text, bar who sent them and when ([phase 10 ADR 4](docs/phase10/adr.md)). See [phase 5](docs/phase5/tdd.md).

`make run FORM=vehicle_log FIXTURE=happy` runs one, `FORM=requisition` by default. Each run is a fresh submission, `fixture-<fixture>-<time>`; `SUBMISSION=<id>` runs on one again. `make doc FORM=<form> ID=<submission>` shows it and its runs.

The trigger wants `Authorization: Bearer <token>`, from Secret Manager's `trigger-token`, and `?workflow=<form>`: `requisition`, `vehicle_log`, `loan_approval` or `write_off`. It names the form, not the workflow; `make start` and `make smoke` send both for you. Classify fetches a requisition's files from Drive as `lekkai@`. See [phase 6](docs/phase6/tdd.md).

Every email is ours, from `lekkai@`: the first on receipt, then replies in its thread. They go to the form's `notify_to` in `terraform/env/<env>.tfvars` and whoever submitted, in our domain only. A loan request's replies go to `directors@` and `lekkai@`. On dev that's `lekkai@`, and every fixture submits as `lekkai@`, so smoke never mails anyone else. A form the trigger can't clean still answers 400, and its run hands over. See [phase 9](docs/phase9/tdd.md).

`?test=true` beside `?workflow=`, on dev or prod, makes a real run that emails only `lekkai@`, and whoever submitted if `test_to` lists them, with `[TEST]` subjects, and is stored with `test: true`: `make run TEST=1`. See [release 1 ADR 3](docs/release1/adr.md).

`make evals` runs ADK's own `adk eval` on expenser against 36 real requisitions, with `agents/expenser/.env`: `CASE=<eval_id>[,<eval_id>]` for some (`make eval-cases` lists them), `RUNS=3` to see its variance, `DETAIL=1` for ADK's tables. It ends with the cases that failed which metric. By hand only: a run of every case costs about 20 cents. See [phase 7](docs/phase7/tdd.md).

Classify calls the model unless a fixture says otherwise, e.g. `"simulate": {"classify": "stub"}` beside the form's keys for the free, canned answer, or `"files"` to fetch the files for real first. `simulate` only works on dev; prod ignores it. `make agent` runs expenser on its own, locally. See [phase 3](docs/phase3/tdd.md).

## Deployment

A PR runs `make check`. Merging to `main` deploys dev, smoke-tests it and plans prod. Tagging that commit (`0.1.0`) releases it to prod. See [phase 2](docs/phase2/tdd.md).

## TODO

- [ ] **Catch a reused requisition.** Flag a Drive file, or a hash of its contents, already attached to an earlier requisition, before the model sees it. The model doesn't catch an old signed requisition on a new claim ([phase 6 ADR 4](docs/phase6/adr.md)). In the attachments bucket, the hash is already in each object's name
- [ ] **Reverse a requisition.** Asked for by whoever submitted it, or by an accountant, and approved before anything is reversed. Someone once filed a second wifi requisition in error, and said so in its comment
- [ ] **Fixtures expire on dev.** Every smoke leaves a dozen submissions and their runs. A 7-day Firestore TTL on dev only, on an `expire_at` set only on fixture runs (their submission ids start `fixture-`), and a second policy on `runs`, since deleting a document leaves its subcollections. Not on prod until we know the feature
- [ ] **Hot to cold storage.** Attachments are read once, when classified. Try Autoclass on the attachments bucket before writing any lifecycle rules
- [ ] **Alert when nobody was told.** Any failed execution (the handover email failing) and any trigger 5xx should email someone right away. Every one counts, not a rate. Handovers aren't alerts: they already emailed someone
- [ ] **Harden: alert when it goes quiet.** If the form's add-on stops calling the webhook, or the trigger refuses everything, no run starts, so nothing fails and nobody hears. ourfos-v2 died that way, of an expired custom domain, unnoticed. A Cloud Monitoring alert on prod, within the free tier: no trigger request in N days, or any trigger 401 or 5xx. Our own front end will contain more of this, but not all of it
- [ ] **Drop `raw` once our own front end posts requisitions.** The form's payload rides beside the clean requisition while the cleaner is new ([phase 5 ADR 2](docs/phase5/adr.md)), and it's what an unreadable form's handover shows ([phase 9 ADR 5](docs/phase9/adr.md)). A front end that validates before it posts needs neither
- [ ] **One bootstrap for a fresh project.** Each phase adds its own "Bootstrapped, once" steps on top of the last. At the end, fold them into one set of instructions that takes a fresh project, after infra has run, to deployable, and test it on one
- [ ] **A post that timed out but landed.** The handover says to check the reference before booking it again, but a person may skip that and book it twice. With the real Mifos, look the reference up before handing over (phase 4's `post-timeout`). And when a post lands after the run ended, email the thread that it landed, with its transaction id
