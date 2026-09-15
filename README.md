# lekka-ourfos

Internal workflows for [Lekka Credit](https://lekkacredit.com), orchestrated
with Google Cloud Workflows.

A form is submitted, something reviews it, it gets filed, and somebody gets a
reply. This repo holds the orchestration — the workflow definitions, the
services those workflows call, and the apps that read the same records.

| Workflow | What it does | Status |
| --- | --- | --- |
| `requisition` | Requisition form → posted Mifos journal entry, one email | Design ([TDD](docs/tdd.md)) |

Other form types — vehicle logs, loan approval requests — are persisted on
arrival and wait. Their workflows come later; nothing is lost in the meantime.

## The shape of it

```
Google Form ─▶ intake ─▶ Workflows execution ─▶ one email, then done
                 │            │
                 │            ├─ classify   (agent, in lekka-ourfos-agents)
                 │            ├─ check      (deterministic, in the workflow)
                 │            ├─ post       (Mifos)
                 │            └─ confirm    (read it back)
                 ▼
             Firestore
```

Two properties the design is built around, both in
[`CLAUDE.md`](CLAUDE.md) as rules:

**Exactly one email per submission, and it is always the last thing that
happens.** It says one of three things — posted and confirmed, handed to you
with the entry to make, or a post we cannot account for. Nothing is sent while
the outcome is still undecided.

**Nothing parks.** No callbacks, no executions waiting overnight on a click.
Either the system finishes the job and tells you, or it stops and tells you,
within about a minute.

## Where things live

| Repo | Owns |
| --- | --- |
| [`lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra) | Project-level: APIs, service identities, the Firestore database, Artifact Registry, quotas, budgets |
| [`lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents) | Agents: Reasoning Engines, agent service accounts, Model Armor, prompts, evals |
| **`lekka-ourfos`** | Workflows, services, apps, Firestore indexes and rules, Cloud Build triggers |

The line between them is the one the infra repo already draws: anything shared
by two consumers in one project belongs to the layer below, or they fight over
it on every apply.

## Layout

```
envs/dev|prod/     Terraform: service accounts, IAM, Firestore indexes, triggers
packages/          shared libraries, never deployed alone
services/          called BY workflows — invoker is the workflow's SA only
apps/              user-facing — behind IAP
workflows/         the definitions, plus fixtures for running them
```

`services/` and `apps/` are separated because the directory decides the IAM
posture. Everything under `services/` is reachable only by the workflow service
account; everything under `apps/` faces people. Making that structural means
the safe default does not depend on anyone remembering it.

## Running things

```bash
make deploy WF=requisition          # seconds — deploys the YAML, builds nothing
make run    WF=requisition DATA=@workflows/requisition/fixtures/over-limit.json
make deploy SVC=mifos               # builds and deploys one service
make last                           # step-by-step history of the last run
```

`ENV` defaults to `dev` and prod refuses without `CONFIRM=yes` — the real path
to prod is a push to `main`. Target names follow
[`lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra)'s
`Makefile`, so the same commands mean the same things across the repos.

There is no Workflows emulator. The loop is deploy-to-dev and read the
execution, which is why `--execution-history-level=execution-history-detailed`
is on by default and why workflow deploys are kept off the Terraform path.

## Docs

- [`docs/tdd.md`](docs/tdd.md) — the design, the data model, the failure
  handling, and the phased implementation plan
- [`CLAUDE.md`](CLAUDE.md) — house rules
