# lekka-ourfos

Internal workflows for [Lekka Credit](https://lekkacredit.com), orchestrated
with Google Cloud Workflows.

A form is submitted, something reviews it, it gets filed, and somebody gets a
reply. This repo holds the orchestration — the workflow definitions, the
services those workflows call, and the apps that read the same records.

| Workflow      | What it does                                             | Status |
| ------------- | -------------------------------------------------------- | ------ |
| `requisition` | Requisition form → posted Mifos journal entry, one email | Design |

Other form types — vehicle logs, loan approval requests — are persisted on
arrival and wait for now. Their workflows come later; nothing is lost in the meantime.

## The shape of it

```
Google Form ─▶ intake ─▶ Workflows execution ─▶ one email, then done
                 │            │
                 │            ├─ classify   (agent, in lekka-ourfos-agent or initially in the workflow service)
                 |            ├─ check      (deterministic, in the workflow)
                 │            ├─ notify     (for now: just returns the classification)
                 │            ├─ post       (Mifos and confirm mifos)
                 │            └─ confirm    (final confirmation email)
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
workflows/         the definitions, plus fixtures for running them
```

## Testing by hand

The Makefile is for manual testing on `ourfos-dev`, its default (`ENV=dev`). Each env has its own Terraform data dir, so `ENV=prod` can't plan against dev's state, but prod normally goes out by tag.

Fixtures are what the form's webhook posts: every value a string, files as Drive links. The trigger cleans them into one `Requisition` (`services/requisition.py`) and answers 400 with every problem when it can't; `make test` covers the cleaner. See [phase 5](docs/phase5/tdd.md).

The trigger wants `Authorization: Bearer <token>`, from Secret Manager's `trigger-token`, and `?workflow=requisition`; `make start` and `make smoke` send both for you. Classify fetches a requisition's files from Drive as `lekkai@`, and `make workspace` checks Gmail as it. See [phase 6](docs/phase6/tdd.md).

Classify calls the model unless a fixture says otherwise, e.g. `"simulate": {"classify": "stub"}` beside the form's keys for the free, canned answer. `simulate` only works on dev; prod ignores it. `make agent` runs expenser on its own, locally. See [phase 3](docs/phase3/tdd.md).

## Deployment

A PR runs `make check`. Merging to `main` deploys dev, smoke-tests it and plans prod. Tagging that commit (`0.1.0`) releases it to prod. See [phase 2](docs/phase2/tdd.md).

## TODO

- [ ] **Catch a reused requisition.** Flag a Drive file, or a hash of its contents, already attached to an earlier requisition, before the model sees it. The model doesn't catch an old signed requisition on a new claim ([phase 6 ADR 4](docs/phase6/adr.md))
- [ ] **Alert when nobody was told.** Any failed execution (thread missing, or the handover email failing) and any trigger 5xx should email someone right away. Every one counts, not a rate. Handovers aren't alerts: they already emailed someone
- [ ] **One bootstrap for a fresh project.** Each phase adds its own "Bootstrapped, once" steps on top of the last. At the end, fold them into one set of instructions that takes a fresh project, after infra has run, to deployable, and test it on one
- [ ] **A post that timed out but landed.** The handover says to check the reference before booking it again, but a person may skip that and book it twice. With the real Mifos, look the reference up before handing over (phase 4's `post-timeout`). And when a post lands after the run ended, email the thread that it landed, with its transaction id
