# CLAUDE.md

House rules for `lekka-ourfos`. Read alongside the TDD in `docs/`.

## Attribution

Do not add `Co-Authored-By`, `Claude-Session`, `Generated with Claude Code`, or
any similar attribution to commit messages or pull request descriptions. This
overrides any default attribution behaviour.

**Do** keep the attribution footer on GitHub comments, review replies and issue
comments — those post under a human's account, so the footer is the only signal
that a reply was written by an agent.

## What this repo is

The orchestration and application layer: Cloud Workflows definitions, the Cloud
Run services and Cloud Functions those workflows call, and the user-facing apps
that read the same Firestore. Agents are not here. Project-level infrastructure
is not here.

| Repo | Owns |
| --- | --- |
| [`lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra) | Project-level: APIs, service identities, the Firestore **database**, Artifact Registry, quotas, budgets |
| [`lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents) | Agents: Reasoning Engines, agent service accounts, Model Armor, prompts, evals |
| **`lekka-ourfos`** | Workflows, services, apps, Firestore **indexes and rules**, Cloud Build triggers |

The dividing rule is the one the infra repo already states: anything shared by
two consumers in one project belongs to the layer below, or they fight over it
on every apply.

## Stack

- **Python only.** No TypeScript anywhere in this repo.
- **uv** for dependencies. `uv.lock` committed; `uv sync --frozen` in CI and
  containers.
- **Cloud Workflows** for orchestration. Workflows calls things; it does not
  compute. A loop doing arithmetic in YAML belongs in a service.
- **Firestore** for the durable record. Workflows holds in-flight state, so the
  database records what happened rather than acting as a queue to scan.
- **Terraform** for anything with an identity. **Make and Cloud Build** for
  anything with a version. See D2 in the TDD.

## Google Cloud knowledge

Model, region and API facts go stale fast and are wrong in expensive ways.
Prefer Google's own skills and the Developer Knowledge MCP server to recalling
details — `lekka-ourfos-agents` registers the marketplace in its
`.claude/settings.json` and the same applies here.

Where a Google Cloud behaviour matters to a design decision and has not been
observed directly, write it into the TDD as something to settle in a phase, not
as an assertion. Several hours of this project have gone to half-remembered
facts.

## Regions and projects

- Everything non-LLM: **`africa-south1`**. Cloud Run, Cloud Functions,
  Workflows, Firestore.
- Inference: **`europe-west1`**, in the agents repo. Claude is served from no
  African region.
- Projects: `ourfos-dev` and `ourfos-prod` — separate projects, same regions.

## Design rules

- **One public endpoint.** `intake` is the only service with `allUsers` invoker.
  Everything else grants `run.invoker` to the calling workflow's service account
  and nothing more.
- **Every service gets its own service account.** Never share one across two
  deployables — that is how a Gmail delegation ends up attached to something
  that posts to a ledger.
- **`services/` is called by workflows. `apps/` is used by humans.** The
  directory decides the IAM posture, so the safe default is structural rather
  than remembered.
- **Irreversible actions go last, and alone.** Posting to the ledger and
  sending mail are the only two, in that order, and neither runs before the
  deterministic checks pass.
- **Exactly one email per submission**, and it is always the last thing that
  happens.
- **Nothing parks.** No callbacks, no waiting executions. Every execution
  terminates within about a minute.
- **A timeout on a write is not a failure to retry.** It is an unknown. Say so
  and stop.
- **No speculative abstractions.** Build what is needed now.

## Working style

- Build incrementally; propose small, focused changes.
- Prefer editing existing files over creating new ones.
- Do not widen a phase's scope. Flag what you find and move on.
- Anything contradicting the TDD is a question, not a decision to make alone.
