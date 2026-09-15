# TDD: Requisition Workflow on Cloud Workflows

**Status:** Draft — for review
**Author:** Lekka Engineering
**Last updated:** 2026-09-15

---

## 1. Summary

A requisition form is submitted. Today it takes a round trip through an inbox,
a suggestion email nobody can reply to usefully, and a posting step that was
written, tested, and then commented out. The ledger is never written.

This document specifies replacing that with a single Cloud Workflows execution
per submission: persist, classify, check, post, confirm, and send **exactly one
email** — always last, saying one of three things. Nothing parks, nothing sits
pending overnight, and the two irreversible actions happen at the end, in that
order, only after deterministic checks have passed.

The working system it replaces is
[`tinopetros/ourfos-v2`](https://github.com/tinopetros/ourfos-v2), with the
model call prototyped in
[`tinopetros/expenser`](https://github.com/tinopetros/expenser). Both are
frozen — no further development — and are the reference for behaviour that must
carry over. The classification itself moves to
[`lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents) and
is out of scope here; this repo calls it.

---

## 2. Background

### 2.1 What runs today

A single Heroku dyno runs three independent `setTimeout` loops against MongoDB.
The form arrives twice — once as a webhook payload, once as a Google Forms
notification email — and the two halves are reunited by matching an exact
subject string.

```
Google Form ──▶ POST /api/webhook/forms ──▶ mongo · Form
            └─▶ Forms notification ──▶ Gmail ──[imap poller, 60s]──▶ mongo · Email
                                              form-matcher, 60s ──▶ joins the two
                                              form-processor, 120s ──▶ Drive → Claude
                                                                   ──▶ suggestion email
                                                                   ──▶ Mifos  ✗ never called
```

`src/email/form-matcher.ts` exists solely to repair an ordering race: the
webhook and the email arrive in either order, so a third loop reconciles them
afterwards. `postOutput()` in `src/email/form-processor.ts` is complete and
commented out; `notes.md` records the intent to re-enable it.

### 2.2 What is wrong with it

| Problem | Consequence |
| --- | --- |
| `posted` and `emailed` are nullable booleans | Four combinations, no defined transitions, and nothing records *why* a requisition is where it is |
| Failures log and return | The next tick retries forever — no backoff, no attempt count, no ceiling |
| `emailed: true` is written *before* the Gmail call | A failed send is never retried. Deliberate, to avoid double-sending, but mail is lost silently |
| Nothing is idempotent | Duplicate avoidance is a rolling 7-day `$nin` scan, which grows with volume and is all that stands between us and a double post |
| One process | A restart mid-model-call leaves no trace the call happened |
| No execution record | "What happened to requisition 482?" means reading logs, if they are still there |

### 2.3 What Workflows gives us

From [`tinopetros/hello-gcp-workflows`](https://github.com/tinopetros/hello-gcp-workflows),
which is the learning ladder this design builds on:

1. **State is persisted after every step.** A failing step is retried alone;
   the expensive steps before it are not repeated.
2. **`try` / `retry` / `except` are per-step**, so each failure mode gets the
   policy it deserves rather than one global loop.
3. **Waiting is free.** `sys.sleep` incurs no time-based charge, which matters
   for exactly one thing here (§8.3).
4. **Execution history is deleted after 90 days.** The engine forgets on
   purpose — which is why §7 keeps an append-only trail of its own.
5. **`retry` is a sibling of `try` and `except`, not nested inside `try`.**
   Cited because the docs and most blog posts get it wrong.

---

## 3. Goals and non-goals

### Goals

- One execution per submission, ending in exactly one email.
- Post to the Mifos ledger, correctly, exactly once — or say plainly that we
  could not tell.
- Persist every submission on arrival, including types no workflow handles yet.
- Ship in phases, each independently useful in production and each unlocking
  one position on a runtime mode dial.
- Make "what happened to submission 482" a single document read.
- Establish the conventions the next Lekka workflow copies.

### Non-goals (this iteration)

- **Classification quality.** The agent's accuracy, its prompts and its evals
  live in `lekka-ourfos-agents`. This repo proves the integration works, not
  that the answer is good.
- **A console approval flow.** Handover is by email and is terminal (D4). The
  parked-callback design is future scope (§12).
- **Reversals.** The prompt already says a disapproval should reverse previous
  work, and the connector will grow a reversal endpoint, but no workflow calls
  it yet.
- **Workflows for the other form types.** They are persisted and wait (D6).
- **Alerting on unknown form types.** Deliberately deferred.
- **Reading the inbox.** Nothing in this design polls or parses email.

---

## 4. Key decisions

### D1 — One Workflows execution per submission, and nothing parks

**Decision.** A form submission starts one execution, which runs nine steps and
terminates. No `events.await_callback`, no parked executions, no pending state.
Every path completes in roughly 15–60 seconds.

**Why.** The contract is narrow enough to hold in your head: *either the system
posts the entry and tells you, or it stops and tells you.* There is no third
state. It also sidesteps the concurrent-execution quota entirely and makes the
90-day history retention a much smaller problem, because nothing is ever
in-flight across days.

**What we give up.** A human cannot approve mid-flow. When checks do not pass,
the automation stops and asks a person to post by hand — which is what they do
today anyway, so the failure mode is the status quo rather than a regression.
The correction signal a console approval would capture is lost for now (§12).

**When this would need revisiting.** The moment approval-in-flow is wanted, the
handover rail becomes `events.await_callback` and the terminal email becomes a
link. That is a change to one step, not a rewrite — `hello-gcp-workflows` rung
8 is already rehearsing it.

### D2 — Terraform owns identity; Make and Cloud Build own versions

**Decision.** Service accounts, IAM bindings, Firestore indexes and rules,
Cloud Build triggers — Terraform. Container images and workflow YAML — not
Terraform. Workflow definitions deploy with `gcloud workflows deploy`.

**Why.** `gcloud workflows deploy` takes a couple of seconds, and that is what
makes the inner loop bearable when there is no emulator. Putting the YAML in
state turns every edit into a plan/apply against a state lock. The same
argument already applies to images, which Cloud Build pushes and Terraform does
not know the digests of.

**The cost, stated plainly.** `terraform apply` on a fresh project does not
give you a running system. It gives you a project shaped to receive one. That
is already true today because of images; this extends it to one more artifact.

### D3 — `intake` persists everything and starts a workflow only if one exists

**Decision.** `intake` writes the submission to Firestore unconditionally, then
starts an execution only if the submission's `type` has a workflow registered
in `config/runtime`. Unknown or unhandled types rest at `NO_WORKFLOW`.

**Why.** Vehicle logs and loan approval requests arrive today and are matched
and stored but never processed. Persist-first means nothing is lost while their
workflows do not exist, and when one ships, its backlog is already in Firestore
waiting for a backfill (§11, phase 1).

**Consequence.** The collection is `submissions/`, not `requisitions/`, with a
`type` field — one collection and a common envelope, so `intake` stays generic
and the console gets a single query for everything that arrived.

### D4 — The type-to-workflow map is runtime config, not code

**Decision.** `config/runtime` holds the map from form type to workflow name.
`intake` reads it; it does not branch on type in code.

**Why.** `intake` is the one publicly reachable service in the system. Adding a
workflow should not require redeploying it. As config, registering a workflow
is a document write, and the degradation is correct by construction: an
unrecognised type persists, starts nothing, and raises no error.

**Note.** The exact form-type strings are not in this document on purpose.
They are configuration, and the current values live in
`src/utils/constants.ts` in `ourfos-v2` (`FORM_TYPES`,
`FORM_SUBJECT_PREFIXES`).

### D5 — Exactly one email per submission, always last

**Decision.** One email, chosen from three mutually exclusive variants by how
the execution ended, sent by the final step before `finalize`. A Firestore
claim spans all three, so a submission can never receive two.

**Why.** Today's suggestion email is sent mid-flow, before anything is decided,
and cannot be replied to usefully. Making the email terminal means everything
before it is internal state that can retry and correct itself without anyone
seeing a half-finished thought.

Full specification in §9.

### D6 — Posting is guarded by a claim, and a timeout is never retried

**Decision.** `post_to_mifos` holds a Firestore claim so only one attempt can
ever write. Connection resets — where the request demonstrably never reached
Fineract — retry three times. A 4xx never retries. **A timeout never retries
blind**: the step sleeps, reconciles against the ledger by listing that day's
entries, and only then decides.

**Why.** A timeout is not a failure, it is an unknown: the write may have
landed. A blind retry on that is how one requisition becomes two journal
entries. Reconciling first is exactly what a person would do, and it converts
a dead end into a decision with three outcomes rather than two.

Full specification in §8.

### D7 — `classify` is called, not implemented here

**Decision.** The workflow calls the `expenser` agent in
`lekka-ourfos-agents` over HTTP with OIDC, passing Drive URIs. The agent
fetches and converts the attachments itself, immediately before the model call.

**Why.** Agents are deliberately black boxes with their own repo, lifecycle,
telemetry and evals. Prompts, the chart of accounts and model choice are theirs.

**Dependency.** The agent's current `Attachment` type carries base64 `data`.
Taking a Drive URI instead is a change on their side, agreed and pending. Phase
2 cannot complete before it lands. The alternative — a service here fetching
Drive and passing bytes — was considered and rejected: it would keep this
repo's surface smaller but leaves the fetch in two places once a second agent
needs attachments.

**What this moves.** Drive domain-wide delegation moves to the agent's runtime
service account, widening an identity the agents TDD deliberately holds to four
roles. That is their call to make and should be explicit in their PR.

### D8 — Three deployables, each with its own service account

**Decision.**

| | Kind | Invoker | Identity carries |
| --- | --- | --- | --- |
| `intake` | Cloud Run | `allUsers` | Firestore write, `workflows.executions.create` |
| `mifos` | Cloud Run, three routes | workflow SA only | Fineract credentials |
| `notify` | Cloud Function | workflow SA only | Gmail DWD (§9.3) |
| `classify` | Vertex agent (other repo) | workflow SA only | — |
| `check` | Workflows expression | — | — |

**Why three, not six.** `post`, `reconcile` and `confirm` share one Fineract
client, one TLS configuration and one secret — that is a service with three
routes, not three deployables that each vendor the client. `notify` is a single
handler with no shared state and a completely different credential, so it stays
separate. Cloud Functions 2nd gen *is* Cloud Run underneath, so this is a
packaging choice, not a runtime one: `notify` needs no container control and
deploys from source.

**Never share a service account across two deployables.** `notify` holds a
Gmail delegation that can impersonate anyone in the domain; `mifos` holds
credentials that move money. A shared identity is how one acquires the other's
reach. Separate deployables make separate identities natural.

### D9 — `check` is deterministic and runs in the workflow

**Decision.** Balance, chart membership and the form-total cross-check are pure
functions evaluated in the workflow itself. No service, no container, no model.

**Why.** This is the auditable layer, and it must never be the model's word
alone. Being pure means a retry cannot change the answer, it costs nothing, and
it is the part that has to be defensible to an auditor.

**One check is new.** The debit total must equal the form's own
`total_amount`. `ourfos-v2`'s `validate()` (in `src/expenser/post.ts`) checks
that debits and credits balance each other, but never against the form. That is
the check that catches a misread image, and it is cheap.

### D10 — The mode dial is the production rollout mechanism

**Decision.** `config/runtime.mode` takes `off`, `shadow`, `review` or `auto`,
read at the start of every execution. Each implementation phase unlocks the
next position.

**Why.** It means shipping a phase to production is a document write, not a
deploy, and reverting is the same write backwards. It also makes "run in shadow
for a month and compare against what the accountant actually booked" a
first-class operating mode rather than a branch someone has to maintain.

Fail closed: if `config/runtime` cannot be read, default to `review`, never to
`auto`.

### D11 — Threading is a requirement, and it costs a read scope

**Decision.** The final email replies into the thread of the Google Forms
notification the submitter already received. Finding that thread needs a Gmail
search, which needs a read scope on `notify`'s delegated identity.

**Why.** The submitter has an email about their submission already. A
disconnected reply fragments the record.

**The cost, accepted knowingly.** `notify` holds `gmail.readonly` — full
message-body access, domain-wide. Mitigations in §9.3, and §12 records the
change that retires it.

### D12 — The Mifos client starts in this repo

**Decision.** `packages/mifos/` inside `lekka-ourfos`, with a hard boundary:
configuration in, HTTP out, no Firestore and no workflow knowledge. A separate
`mifos-connector-py` is in progress; when it is published and a second Python
consumer exists, this package is deleted and replaced by the dependency.

**Why.** Today `lekka-ourfos` is the only Python consumer — the agents repo
states "No Mifos" explicitly. A publishing pipeline in phase 5's critical path
serves a consumer that does not exist yet. If the boundary holds, swapping the
implementation for the package is mechanical.

**Distribution, when it happens.** Public PyPI with Trusted Publishing is the
recommendation: a Fineract client contains no Lekka IP — credentials, the chart
of accounts, the prompts and the business rules all live elsewhere — and public
PyPI is the only option that needs no auth configuration in *any* build
context, including an Agent Runtime container build that cannot carry an SSH
key or a PAT. That matters because the agents TDD already says ledger posting
eventually becomes an agent. Artifact Registry is the fallback if privacy is
wanted; installing from git is not, for the build-credential reason. Two things
to settle before a first publish: the package name, and an actual read-through
for anything sensitive, because a PyPI release can be yanked but not unpublished.

---

## 5. Architecture

### 5.1 Repository layout

```
lekka-ourfos/
  docs/tdd.md
  CLAUDE.md
  Makefile                      two axes: WF= and SVC=
  cloudbuild/
    service.yaml                one spec, parameterised by _SERVICE
    workflows.yaml              deploys every workflow definition
  envs/
    dev/   prod/                Terraform. State: app/dev, app/prod
  packages/
    mifos/                      Fineract client (D12)
    firestore/                  the submission document, the status enum, accessors
    forms/                      form types and payload shapes
  services/
    intake/   mifos/   notify/
  apps/
    console/                    read and audit surface (later)
  workflows/
    requisition/
      workflow.yaml
      fixtures/*.json
```

`packages/firestore` is what stops the console and the workflow disagreeing
about what `HANDED_OFF` means. Both import it.

Terraform state goes in the existing buckets — `ourfos-dev-tfstate` and
`ourfos-prod-tfstate` — under prefixes `app/dev` and `app/prod`, alongside the
infra repo's `infra/*` and the agents repo's `agents/*`.

### 5.2 The nine steps

```
Google Form submitted
  │  form JSON + shared-secret header
  ▼
1 intake ─── Cloud Run, public ─── writes submissions/{id} @ RECEIVED
  │          no workflow for this type? → NO_WORKFLOW, stop
  │  starts execution named {id} — a replayed webhook re-uses it
  ▼
┌─── ONE WORKFLOWS EXECUTION ────────────────────────────────────────┐
│                                                                    │
│  2 load_config      config/runtime → mode, autoPostLimit, …        │
│       │             mode=off → SKIPPED, stop                       │
│       ▼                                                            │
│  3 classify         Vertex agent, Drive URIs in                    │ ──┐
│       │             → {approve, reason, debit[], credit[]}         │   │
│       ▼                                                            │   │
│  4 check            balanced · GL ids in chart · debits = total    │ ──┤
│       │             → {ok, violations[]}                           │   │
│       ▼                                                            │   │
│  5 route            ok + auto + under limit → post                 │ ──┤
│       │             mode=shadow → SHADOW_ONLY, stop                │   │
│       ▼                                                            │   │ handover
│  6 post_to_mifos    claim · POST · referenceNumber={id}            │ ──┤ rail
│       │             timeout → sleep → reconcile → decide (§8)      │   │
│       ▼                                                            │   │
│  7 confirm          list by transactionId · lines, amounts, reversed│──┤
│       │                                                            │   │
│       ▼                                                            │   │
│  8 send_email  ◀───────────────────────────────────────────────────────┘
│       │             the only email · one of three variants (§9)    │
│       ▼                                                            │
│  9 finalize         terminal status + audit event                  │
└────────────────────────────────────────────────────────────────────┘
```

Five steps can exit onto the handover rail, and the rail ends at `send_email`
— never at silence. That is the property worth protecting in review: **no
failure path terminates without sending something.**

### 5.3 Infrastructure

Terraform in this repo provisions, per environment:

- Service accounts: `intake`, `mifos`, `notify`, and the workflow's own.
- `run.invoker` for the workflow SA on `mifos`; the Cloud Functions equivalent
  on `notify`; `allUsers` on `intake` and nowhere else.
- `aiplatform.user` for the workflow SA on the agent resource.
- Firestore indexes and security rules (the *database* is the infra repo's).
- Secret Manager entries for the Fineract credentials and the intake shared
  secret; accessor bindings to the one service account that needs each.
- Cloud Build triggers, path-filtered per service (§11).

The Firestore database, the Artifact Registry repositories, the Cloud Build
GitHub connection, quotas and budgets are all
[`lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra)'s.
One per project, shared by more than one consumer — the same rule that repo
already applies to APIs.

Region: `africa-south1` for everything here. Inference is `europe-west1` in the
agents repo, so there is a cross-region hop at `classify` — irrelevant against
a model call measured in tens of seconds.

### 5.4 Configuration: topology at deploy time, policy at runtime

Service URLs are resolved at deploy time
(`gcloud run services describe --format='value(status.url)'`) and substituted
into the workflow YAML before `gcloud workflows deploy`. A wrong URL then fails
a deploy rather than an execution at 2am.

Mode, `autoPostLimit`, the type-to-workflow map and prompt version live in
`config/runtime` and change without a deploy.

The rule: **anything you would want to change without shipping is runtime
config; anything describing the shape of the system is baked in at deploy.**

---

## 6. Step contracts

| # | Step | Runs on | In | Out | Typical | Retry |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `intake` | Cloud Run | Forms payload + HMAC | 200, execution started | 150–400 ms | Caller retries; create-if-absent makes a replay a no-op |
| 2 | `load_config` | Workflows | `config/runtime` | mode, limit, versions | 100–300 ms | Default; fail closed to `review` |
| 3 | `classify` | Vertex agent | subject, form body, Drive URIs | decision + tokens, latency | 8–40 s | 2×, 4 s then 16 s; then hand over |
| 4 | `check` | Workflows | decision + form total | `{ok, violations[]}` | <200 ms | None — deterministic |
| 5 | `route` | Workflows | mode, ok, total | a jump | immediate | N/A |
| 6 | `post_to_mifos` | Cloud Run | entry + `referenceNumber` | `{transactionId}` | 1–5 s | See §8 — **not** a simple policy |
| 7 | `confirm` | Cloud Run | `transactionId` | the recorded lines | 0.5–2 s | 3×, freely — it is a read |
| 8 | `send_email` | Cloud Function | one of three outcomes | `{messageId, threadId}` | 1–3 s | 2× on 5xx, behind the claim |
| 9 | `finalize` | Workflows | the execution | result | <300 ms | Default |

**`intake`** derives `submissionId` from the form slug and response number, so
a replayed webhook re-uses the same document and the same execution name. It
coerces types at the edge — the rung-1 lesson from `hello-gcp-workflows` is
that real webhooks send `"42"` as a string and Workflows comparisons do not
coerce.

**`classify`** is retried at temperature 0, so a retry is the same call. Two
attempts, then hand over — there is no value in a third.

**`confirm`** is a real verification, not a formality. The create response
carries a `transactionId` and nothing about what was booked. Listing by that
id returns every line of the transaction — at least two, since it balances —
and we assert the count equals debits plus credits, the amounts match what we
sent, and nothing came back reversed. `ourfos-v2` already did the count check
in `post()`; this keeps it and adds the rest.

---

## 7. The record

### 7.1 Firestore

```
submissions/{submissionId}              id = form slug + response number
  type            REQUISITION · VEHICLE_LOG · LOAN_APPROVAL_REQUEST
  status          RECEIVED → CLASSIFIED → CHECKED → POSTED → CONFIRMED
                            → NOTIFIED → DONE
                  terminal handovers   HANDED_OFF · POST_UNCERTAIN
                                       · POSTED_UNCONFIRMED · NOTIFY_FAILED
                  resting              NO_WORKFLOW
                  disabled paths       SKIPPED · SHADOW_ONLY
  form            { payableTo, totalAmount, dateDisbursed, submitter, raw }
  sources         [ driveUri ]            what the agent was handed, for replay
  decision        { approve, reason, debit[], credit[], comments[],
                    model, promptVersion, tokens, latencyMs }
  checks          { ok, violations[] }
  handover        { reason, atStep, at }
  mifos           { claim, referenceNumber, transactionId, lineCount, postedAt }
  notify          { claim, variant, messageId, threadId, threaded, sentAt }
  execution       { id, startedAt, completedAt, attempts{} }
  config          { mode, autoPostLimit, promptVersion }   as read at step 2

submissions/{submissionId}/events/{id}  append-only: at, from, to, actor, note

config/runtime    mode · autoPostLimit · typeToWorkflow{} · promptVersion

hardCases/{submissionId}                every HANDED_OFF input, for the backlog
```

### 7.2 Why this and not a port of the Mongo schema

- **One document, one read.** Today the console would join `Form`, `Email` and
  `ModelOutput` across an exact subject-string match.
- **A status, not two booleans.** `posted` and `emailed` become one enum with
  defined transitions, so an impossible state is unrepresentable rather than
  merely unlikely.
- **No `Email` collection.** Gmail is the system of record for mail. We keep a
  message id and a thread id — pointers, not copies of bodies and replies.
  Nothing in this design reads an inbox, so there is nothing to populate it
  with and nothing that would query it.
- **No attachment storage.** Drive URIs are stable and the agent fetches them
  in-step. We record what it was handed, not the bytes.
- **Two claims, two guarantees.** `mifos.claim` means at most one write to the
  ledger; `notify.claim` means at most one email. They are the only two places
  concurrency can hurt us.
- **The events subcollection outlives Workflows.** Execution history is
  retained 90 days; a posted journal entry needs a trail for rather longer.
- **`config` is snapshotted onto the submission**, so a decision can be
  replayed against the settings that produced it.

### 7.3 `hardCases`

Every `HANDED_OFF` input is written to `hardCases/`. v1 cannot capture the
*right* answer — there is no console to record one in — but it captures every
input the model could not handle, which is the half of an eval set that is hard
to collect deliberately. The answer key arrives with the console (§12).

---

## 8. Posting to the ledger

The only step that moves money, and the only one where a retry can do damage.

### 8.1 The write

`POST /journalentries` with `referenceNumber = submissionId`. A Firestore
transaction claims `mifos.claim` first; only the attempt that wins the claim
may write. On success the same transaction records `transactionId` and releases
the claim.

`referenceNumber` does not make a retry safe. It makes the reconciliation in
§8.3 possible and a human's check take ten seconds instead of ten minutes.

### 8.2 Retry policy, by failure

| Failure | Retry | Reasoning |
| --- | --- | --- |
| Connection reset before the request left | 3× | Demonstrably never arrived |
| 4xx | Never | The payload is wrong, not the network |
| 5xx | 3× | The server rejected it without booking |
| **Timeout** | **Never blind** | It may have landed. See below |

### 8.3 The unanswered post

```
        POST ──timeout──▶ sleep ~45 s ──▶ list that day's entries
                                              │
                          ┌───────────────────┼───────────────────┐
                          ▼                   ▼                   ▼
                    one match            no match            ambiguous
                 record the id,      the write never       nothing, or
                 carry on to         landed — post         more than one
                 confirm             again (max 2          candidate
                                     attempts total)            │
                                                                ▼
                                                        POST_UNCERTAIN
                                                        + email a person
```

Three details decide whether this is safe:

**The sleep is not optional.** A timed-out POST may still be committing. Read
immediately, see nothing, conclude "did not land", retry — and now there are
two. Roughly 45 seconds, and it costs nothing at the Workflows level.

**The block lives in the workflow, not in the service.** `post_to_mifos` is one
named step whose `except` sleeps and calls the reconcile route. Two reasons: the
sleep is free in Workflows and billable inside a Cloud Run request, where it
also eats the request timeout; and the two HTTP calls appear separately in
execution history, so you can see that reconcile ran and what it found.

**Matching.** `referenceNumber` is present on the read type but is *not* a
query parameter — `ListJournalEntriesParams` in `mifos-connector-ts` has
`fromDate`/`toDate`, `officeId` and `transactionId`, and no reference field. So
reconcile lists the day's entries and filters client-side on `referenceNumber`.
There is no better option to have missed.

**Timezone.** "That day" must mean the day Fineract stamped. `ourfos-v2`'s
`formatDate()` uses local server time; on GCP that is UTC, while Zimbabwe is
UTC+2, so a 01:00 CAT posting is the previous day in UTC. This affects the
search window and is a latent bug in the existing posting path. Get it right
here rather than inheriting it.

### 8.4 Ambiguity is an outcome, not an error

Two identical small requisitions on the same day are genuinely
indistinguishable without a reference on both. When reconcile cannot tell,
`POST_UNCERTAIN` is the honest answer, the email carries the candidate entries,
and a person decides. This is rare; it is not impossible; and guessing is worse.

---

## 9. The email

### 9.1 Three variants, one send

| Outcome | Goes to | Says |
| --- | --- | --- |
| `DONE` | the requisition thread | What was posted, the accounts it hit, and the transaction id |
| `HANDED_OFF`, checks **passed** | the requisition thread | **Here is the entry to make** — these debits, these credits, it balances. Please key it in |
| `HANDED_OFF`, checks **failed** | the requisition thread | Here is what we got and the rule it broke. A starting point, not a recommendation |
| `POST_UNCERTAIN` | the ledger owner, **off-thread** | A post went unanswered. Check whether `{submissionId}` exists before booking it again |

The second row is why phase 4 is useful on its own. A validated, balanced,
GL-coded entry delivered to a person is most of the value of this system, with
no write access to Mifos anywhere in it. Sitting there for a month while the
disagreement rate is watched is a legitimate outcome, not a stalled project.

`POST_UNCERTAIN` goes off-thread because the submitter cannot help with it and
should not be asked to. It is the one email here that must not sit unread.

### 9.2 Sending exactly once

A Firestore transaction moves `notify.claim` from `pending` to `sending`; only
the attempt that wins the move sends. The claim spans all three variants, so a
submission cannot receive two. A crash mid-send leaves `sending` — visible and
queryable, never a silent double-send. Two retries on 5xx, behind the claim.

This is the inverse of `ourfos-v2`, which sets `emailed: true` *before*
calling Gmail (`form-processor.ts`, `emailOutput`). That avoids double-sends by
losing failed ones silently. The claim gets both.

### 9.3 Finding the thread

The Google Forms notification stays enabled — it is fallback coverage while
this system is new.

Search on the **response number**, not the whole subject:
`subject:"#482" newer_than:7d`. `ourfos-v2` built subjects as
`{form_name} - {payable_to} - #{response_number}` and matched them exactly, but
`payable_to` is free text and the form name is editable, while the response
number is a number Google generates.

**Scope.** `notify` holds `gmail.send` and `gmail.readonly`. Mitigations:

- Domain-wide delegation is authorised per service-account client id in the
  Workspace admin console, so the read scope attaches to `notify`'s identity
  alone — not `mifos`, not `intake`, not the agent.
- The search is bounded to 7 days, so what it reads in practice is far narrower
  than what the scope permits.
- No message content in logs or spans. The thread id is the only thing kept.

> **Settle in phase 4.** `gmail.metadata` may not permit the `q` parameter on
> `messages.list`. If it does, the scope narrows to headers-only and should.
> Verify empirically and record the answer — it changes the IAM posture, not
> the design.

**A miss is recorded, not silent.** If no thread is found, still send — the
email is the deliverable — and stamp `notify.threaded: false`. Otherwise the
week the subject format changes, threading stops and nobody notices for a
month.

---

## 10. Failure routing

Workflows retries the failing step alone. Once retries are spent, every row
lands in the same place: an email, then the end of the execution.

| What went wrong | Retry | Terminal status | The email asks for |
| --- | --- | --- | --- |
| Drive file missing or permission denied | 3× | `HANDED_OFF` | Check the Drive link, post by hand |
| Model overloaded or rate-limited | 2× | `HANDED_OFF` | No classification this time; form attached |
| Model output unparseable | 2× | `HANDED_OFF` | Same, raw output kept for the prompt backlog |
| Unbalanced, or a GL id not in the chart | None | `HANDED_OFF` | The draft and the rule it broke |
| Debits ≠ the form's stated total | None | `HANDED_OFF` | Same — the misread-image check |
| Over `autoPostLimit`, or `mode: review` | N/A | `HANDED_OFF` | **The validated entry to key in** |
| Mifos 4xx | None | `HANDED_OFF` | Fineract rejected it, body quoted |
| Connection reset before the request left | 3× | `HANDED_OFF` | Could not reach Fineract; nothing written |
| **Mifos timeout** | **None blind** — §8.3 | `POST_UNCERTAIN` | Check `{submissionId}` before re-booking |
| Entry will not read back, or does not match | 3× on the read | `POSTED_UNCONFIRMED` | Posted but unverified; please eyeball it |
| Gmail send fails | 2×, behind the claim | `NOTIFY_FAILED` | Nothing — it pages instead |

`NOTIFY_FAILED` is the one failure that cannot announce itself, which is why it
is the only one that alerts rather than emails.

**Alert thresholds are absolute, not rates.** This system runs perhaps 10–20
requisitions a week; one failure is 5% of a week, so percentage-based alerting
is noise. Any `POST_UNCERTAIN`, any `POSTED_UNCONFIRMED`, any `NOTIFY_FAILED`
alerts immediately. Handover rate is a weekly report, not an alert — too noisy
to page on, too important not to look at.

---

## 11. Implementation phases

Each phase is scoped to be picked up independently, including by a different
agent. Phases are sequential — each assumes the previous is merged — but within
a phase the work is self-contained. **Each phase is trialled on `ourfos-dev`
and then promoted to `ourfos-prod`**, where the promotion is a `mode` change on
`config/runtime`, not a deploy.

**Context every phase needs.** Read this TDD and `CLAUDE.md` first, then:

- [`tinopetros/ourfos-v2`](https://github.com/tinopetros/ourfos-v2) — the
  system being replaced. **Frozen**, so specific files are safe to cite:
  `src/expenser/post.ts` (`validate()`, the payload shape, `formatDate()`),
  `src/email/form-processor.ts` (the reply body, the commented-out
  `postOutput()`), `src/utils/constants.ts` (form types and subject prefixes),
  `src/routes/form-webhook.ts` (how the subject is built).
- [`tinopetros/expenser`](https://github.com/tinopetros/expenser) — the model
  prototype. **Frozen.** Prompts and eval snapshots; the agent repo owns them now.
- [`tinopetros/mifos-connector-ts`](https://github.com/tinopetros/mifos-connector-ts)
  — the API shape to mirror in Python. Under active development: take the
  shape, do not assume a given line survives.
- [`tinopetros/hello-gcp-workflows`](https://github.com/tinopetros/hello-gcp-workflows)
  — Workflows patterns and the Makefile idiom. Active.
- [`tinopetros/lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra)
  — what already exists underneath, and the Makefile spine to copy. Active.
- [`tinopetros/lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents)
  — the `classify` contract. Active, and D7 depends on a pending change there.

**Standing rules.** Python only. One public endpoint. One service account per
deployable. Irreversible actions last and alone. Do not widen a phase's scope —
flag and move on. Anything contradicting this TDD is a question, not a decision
to make alone.

### Testing, across all phases

Three tiers, following the split that works in `lekka-ourfos-agents`:

- **No credentials.** `submissionId` derivation, `check` in all its cases,
  email template rendering, payload coercion, boundary type validation,
  reconcile's matching logic against canned entry lists. Most of the suite.
- **Recorded fixtures.** Real Firestore, Gmail and Fineract responses captured
  once and replayed, so parsing is verified against real output with no live
  call.
- **Live, against `ourfos-dev`.** Deploy-and-run, reported rather than
  self-verified where deploy access is needed.

**70% line coverage** is the bar, gated in CI. The suite is only worth trusting
if it fails when the code breaks: deliberately break a matcher and confirm a
test goes red.

**`post_to_mifos` needs its own answer**, because the honest test writes to a
ledger. Fixtures for the client, a dev Fineract instance for integration, and a
post-then-reverse test for genuine end-to-end — which needs the reversal
endpoint the connector does not have yet. If it has not landed by phase 5,
phase 5 tests against fixtures and a dev instance, and says so.

---

### Phase 0 — Review and merge this TDD

**Implementation.** Review. Merge.

**Testing.** None. Sign-off is the gate.

**Done when** merged.

---

### Phase 1 — Intake and the record

**Scope.** A form submission arrives and lands correctly in Firestore. No
workflow runs. This phase isolates the public edge and the data model from
everything else.

**Implementation.**

- Repo skeleton per §5.1: `Makefile` (spine from `lekka-ourfos-infra`'s —
  `check-env`, help-as-default-goal, `-chdir=`; packaging idiom from
  `hello-agent-deployment/tf-adk`'s `$(PACKAGE): $(AGENT_SRC)` dependency
  trick), `envs/dev|prod` Terraform with state at `app/{env}`, `uv` with
  `uv.lock` committed.
- `packages/forms`: form types and payload shapes, ported from
  `ourfos-v2/src/utils/constants.ts`.
- `packages/firestore`: the submission document, the status enum, accessors.
  This is the shared vocabulary — write it once, import it everywhere.
- `services/intake`: HMAC verification with a timestamp in the signed payload
  (replay protection), type coercion at the edge, create-if-absent write,
  `submissionId` derivation, and the `config/runtime` type-to-workflow lookup.
  Unregistered types rest at `NO_WORKFLOW`.
- Terraform: the `intake` service account, `allUsers` invoker, the shared
  secret in Secret Manager, Firestore indexes and rules.
- A rate limit on `intake`. It is the only thing on the internet.
- `make backfill WF=<name>` — starts executions for `NO_WORKFLOW` submissions
  of a given type. Not needed yet; written now because it is five lines now and
  a scramble the day vehicle-log ships.
- Cloud Build: the path-filtered trigger for `intake`, and the workflows
  trigger.

**Testing.**

- A real form submission from `ourfos-dev` produces a correct document —
  every field, right types, `RECEIVED`.
- The same webhook delivered twice produces one document and one execution.
- A `VEHICLE_LOG` submission persists at `NO_WORKFLOW` and starts nothing.
- A bad HMAC is rejected; a replayed timestamp is rejected.
- `"42"` in a numeric field arrives as a number, not a string.
- Firestore rules deny direct client access.
- Promote to `ourfos-prod` and confirm real submissions land.

**Done when** production submissions of every type are landing correctly in
Firestore, and nothing else has been built.

---

### Phase 2 — Classify

**Scope.** The workflow exists and calls the agent. One step of real work.

**Implementation.**

- `workflows/requisition/workflow.yaml`: `load_config`, `classify`, `finalize`.
  Deployed by `make deploy WF=requisition`, not by Terraform (D2).
- The workflow's service account; `aiplatform.user` on the agent resource;
  `run.invoker` nowhere yet.
- Deploy-time URL substitution (§5.4).
- `fixtures/` with real payloads for `make run`.
- The `classify` call: Drive URIs in, decision out, recorded on the submission
  with model, prompt version, tokens and latency.
- Retry: 2× at 4 s and 16 s; exhausted → `HANDED_OFF` with no email yet (phase
  4 sends it). Record the handover reason regardless.

**Depends on** the agent accepting Drive URIs (D7). Confirm it has landed
before starting.

**Testing.**

- A real requisition produces a decision recorded against the submission.
- Token counts and latency are present and plausible.
- A deliberately broken agent URL fails visibly, not silently.
- An agent timeout exhausts retries and lands at `HANDED_OFF`.
- Trace context propagates to the agent — its span and the execution join up.
- Promote to prod. Every requisition is classified and recorded; nothing acts
  on it.

**Done when** production requisitions carry a recorded decision, and this
phase has said nothing about whether that decision is any good.

---

### Phase 3 — Check and route  ·  unlocks `mode: shadow`

**Scope.** Deterministic judgement. Still nothing acted on, but now the system
has an opinion it can be measured against.

**Implementation.**

- `check` as a pure Workflows expression or subworkflow (D9): balance to the
  cent, every `glId` present in the pinned chart, debits equal the form's
  `total_amount`, and the salary/payroll exclusion. Port the balance logic from
  `ourfos-v2/src/expenser/post.ts` `validate()`; the form-total check is new.
- `route`: the switch over `mode`, `ok` and the total. `off` → `SKIPPED`,
  `shadow` → `SHADOW_ONLY`, everything else → the handover reason recorded.
- Violations recorded as sentences, because they become the email body in
  phase 4.
- `config/runtime` seeded in both projects with `mode: shadow`.

**Testing.**

- Every violation class produces its own recorded reason. One test per rule.
- A known-good requisition passes all checks.
- The form-total check catches a decision whose debits do not match the form.
- `mode: off` stops at `SKIPPED` and does nothing else.
- Promote to prod in `shadow`. Let it run. **Compare recorded decisions against
  what the accountant actually booked** — this is the accuracy data the whole
  rollout depends on, and it is the first phase that produces it.

**Done when** production runs in shadow and the comparison is being collected.

---

### Phase 4 — The email  ·  unlocks `mode: review`

**Scope.** Close the loop with a human. No ledger write anywhere in this phase.

**Implementation.**

- `services/notify` as a Cloud Function, its own service account, Gmail DWD.
- Thread search per §9.3, bounded to 7 days, on the response number.
- The three email templates. The `HANDED_OFF` variants are the work here:
  checks-passed carries the validated entry ready to key in; checks-failed
  carries the draft and the rule it broke, clearly marked as not validated.
- The send claim (§9.2). This is the part to get right — write the transaction
  carefully and test the crash-mid-send path.
- `send_email` and `finalize` steps; the handover rail wired from `classify`,
  `check` and `route`.
- `NOTIFY_FAILED` alerting.
- Settle the `gmail.metadata` question (§9.3) and record the answer.

**Testing.**

- Each of the three variants renders correctly and lands in the right place.
- The reply threads onto the original Forms notification.
- A submission whose thread cannot be found still gets its email, with
  `threaded: false` recorded.
- Two concurrent sends produce one email. Force it.
- A crash between claim and send leaves `sending` and is queryable.
- No message content in logs or spans.
- Promote to prod in `review`. **Every requisition now hands over with the
  entry to make.** This is a complete product; sitting here for a month is a
  legitimate outcome.

**Done when** production is in `review` and the accountant is keying in entries
this system validated.

---

### Phase 5 — Post to Mifos  ·  unlocks `mode: auto`

**Scope.** The ledger. Everything around it is already proven on real traffic,
so a failure here is unambiguously Mifos.

**Implementation.**

- `packages/mifos`: the Python client (D12). Mirror `mifos-connector-ts`'s
  shape — a client taking config, resources hanging off it with `get`, `list`,
  `create`. Journal entries are all that is needed now.
- `services/mifos` with three routes — `post`, `reconcile`, `confirm` — one
  service account, Fineract credentials from Secret Manager. Remove
  `rejectUnauthorized: false`; the old client's TLS shortcut does not carry
  over.
- The claim (§8.1), the retry policy (§8.2), and the reconcile block inside
  step 6 as a Workflows `try`/`except` with the sleep at the workflow level
  (§8.3).
- Timezone handling for the reconcile window (§8.3) — CAT, not the server's UTC.
- `confirm` per §6.
- `autoPostLimit` seeded; `mode: auto` available but not necessarily on.

**Testing.**

- A clean requisition posts, confirms and emails — end to end on a low-value
  real entry, verified in Mifos, then reversed.
- The reconcile paths, forced: one match, no match, ambiguous. Simulate the
  timeout; do not wait for a real one.
- A 4xx does not retry. A connection reset does. A timeout never posts twice —
  this is the test that matters most.
- `confirm` catches a line-count mismatch and an already-reversed entry.
- Over-limit requisitions still hand over rather than posting.
- Promote to prod in `review` first — phase 5 deployed does not mean
  `mode: auto` on. Flip to `auto` deliberately, when the shadow and review data
  says to.

**Done when** `mode: auto` posts production requisitions correctly, and the
timeout path has been exercised rather than reasoned about.

---

## 12. Future improvements

Not in scope, recorded so they are not lost.

- **Own the thread.** Turn off the Google Forms notification and have `intake`
  send the acknowledgement itself, capturing its own `threadId`. `notify` then
  needs `gmail.send` alone — **this is what retires the `gmail.readonly` scope
  in D11**, which is the reason to do it rather than a nice-to-have. Two sends,
  same inbox volume, nothing to break when a form title changes.
- **The console as an approval surface.** The handover rail becomes
  `events.await_callback`; the terminal email becomes a link. This is where the
  correction signal D1 gives up comes back, and where `hardCases` gets its
  answer key.
- **Reversals.** A second, much shorter workflow triggered from the console
  against a posted submission — not a branch of this one, which by then has
  ended.
- **Workflows for the other form types.** The shape here — classify, check,
  route, act, confirm, notify — is generic. Whether they become parameters of
  one workflow or separate definitions is worth deciding at the second one, not
  the first.
- **Alerting on unknown form types**, so a typo'd type does not accumulate
  silently for six months.
- **`mifos-connector-py` as a published dependency** (D12), when a second
  Python consumer exists.
- **Chart of accounts from source.** It is a literal in the agent's prompt and
  will drift from the ledger. Noted here because `check` validates against it
  too, so the drift has two victims.

---

## 13. Open questions

**Q1 — The ledger owner for `POST_UNCERTAIN`.** Needs a named person or a
monitored alias. It is the one email whose recipient is not derived from the
form, and the one that must not sit unread. Blocks phase 5.

**Q2 — `autoPostLimit`, in dollars.** Needed before `mode: auto`, not before
phase 5 ships. The shadow and review data should inform it.

**Q3 — Does `gmail.metadata` permit `q` on `messages.list`?** Settled
empirically in phase 4 (§9.3). Changes the IAM posture, not the design.

**Q4 — Firestore location.** `africa-south1` per `CLAUDE.md`, but it is chosen
once and never changed, so it wants a deliberate confirmation rather than a
default. Blocks phase 1.

**Q5 — Does the reversal endpoint land before phase 5?** It changes the
post-then-reverse test strategy, not the design.

---

## 14. References

- [`tinopetros/ourfos-v2`](https://github.com/tinopetros/ourfos-v2) — the system being replaced (frozen)
- [`tinopetros/expenser`](https://github.com/tinopetros/expenser) — the model prototype (frozen)
- [`tinopetros/mifos-connector-ts`](https://github.com/tinopetros/mifos-connector-ts) — the client shape to mirror
- [`tinopetros/hello-gcp-workflows`](https://github.com/tinopetros/hello-gcp-workflows) — Workflows patterns
- [`tinopetros/lekka-ourfos-infra`](https://github.com/tinopetros/lekka-ourfos-infra) — the project underneath
- [`tinopetros/lekka-ourfos-agents`](https://github.com/tinopetros/lekka-ourfos-agents) — the `classify` agent
- [Cloud Workflows syntax reference](https://cloud.google.com/workflows/docs/reference/syntax)
- [Workflows connectors](https://cloud.google.com/workflows/docs/connectors)
- [Apache Fineract API](https://fineract.apache.org/)
