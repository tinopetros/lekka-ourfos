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
apps/              user-facing — behind IAP
workflows/         the definitions, plus fixtures for running them
```
