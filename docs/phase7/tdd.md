# Phase 7: evals

## Goal

- A number for how well expenser classifies real requisitions, and a way to raise it: hillclimb the prompt, one change at a time
- Most dangerous first: a false approval, a wrong amount, a wrong account. Each is a hard fail. A false rejection costs a handover, and is reported on its own
- Attachments get a home of their own: a GCS bucket per project, read through one `fetch(ref)` alongside Drive, ready for our own front end

## Shape

```
make evals ─▶ pytest services/evals ─▶ AgentEvaluator("evals.expenser")
                                          │
                                          App(expenser's root_agent,
                                              plugins=[Attachments, expenser's Model Armor])
                                          │   Attachments: gs:// refs in the requisition ─▶ bytes,
                                          │   through classify's own load and turn()
                                          ▼
                                       custom metrics ─▶ pass rate per metric, failing and rounded cases listed

form ─▶ trigger ─▶ workflow ─▶ classify ─▶ fetch(ref) ─┬─ bare id ─▶ Drive, as lekkai@   (as phase 6)
                                                        └─ gs://    ─▶ the attachments bucket
```

- The workflow, its steps and statuses are phase 6's. Only where a file can come from changes

## Already on this branch

- The trigger wants `?workflow=requisition`: it picks the cleaner and the workflow, one webhook URL per form. A missing or unknown one is a 400. Smoke checks it
- `submitted_at` comes from the form's `created_at`, epoch milliseconds in UTC, not its zoneless `response_date`

## The attachments bucket

- `ourfos-dev-attachments` and `ourfos-prod-attachments`, in `africa-south1`. Made in lekka-ourfos-infra, like the sources bucket
- Uniform bucket-level access, public access prevention enforced, Google's default soft delete, no versioning: an object is named by its content, so it never changes
- Named by where it came from: `requisitions/<requisition id>/<field>/<sha256>`. Metadata repeats `source`, `id` and `field`. The content type is set on upload, never guessed from a name
- Evals live in dev only: `evals/requisitions/<case>/<field>/<sha256>`. Prod never holds test data
- Who reads, on the bucket, not the project: `ourfos-services` in both. In dev, me and `ourfos-build` too
- Nothing writes to it from code yet. The front end will; the eval files go up once (see Bootstrapped, once)

## One fetch

- `attachments.load` calls `fetch(ref)` for each file. A bare id is Drive, as today. `gs://<bucket>/<object>` is GCS
- Only our own bucket: any other is a 422 naming the file. A client will soon post these, and the services account must not read whatever else it can reach
- GCS errors map as Drive's do: 429 and 5xx pass through for the workflow to retry, anything else is a 422 and a handover
- Everything after the fetch is phase 6's: `normalize`, `check`, `SHOWN`, `MAX_BYTES`, one turn with a label per field
- The trigger's cleaner keeps `gs://` refs as they are, beside the Drive ids it pulls out of links
- No migration: every stored requisition's bare ids still mean Drive
- `services/integrations/gcs.py` beside `workspace/`. The bucket's name comes from `ATTACHMENTS_BUCKET`, set by Terraform

## The cases

- From expenser's `.eml` files (`src/expenser/tests/evals/inputs/`), each a form notification: fields, and Drive links per field. The local files match the links in order
- Expected answers from expenser's `answers.ts` and `answers.csv`, the ledger as it was posted. The ledger is the answer, odd entries included (ADR 6)
- About 34 cases:
  - the 31 or so distinct requisitions across both folders
  - Makora three times, one attachment each: JPEG, PNG and PDF. Its `.jpg`, `[1].jpg` and `[2].jpeg` are the same bytes, so they're one case
  - Salaries and Salaries Fake, both rejected, for different reasons: a salary is never filed, and Fake's attachment is Mr saruchera's consultancy requisition, not a payroll
- Each case carries a `why` in its expected `reason`, for whoever reads a failure. Not scored
- Converted once by a script in scratch, not kept: the evalset is the source of truth, and edits happen there
- `submitted_by` stays the real address, as `happy`'s does. The model doesn't read it for anything

### An eval case

`services/evals/requisitions.evalset.json`, ADK's `EvalSet`:

```json
{
  "eval_set_id": "requisitions",
  "eval_cases": [{
    "eval_id": "bhola-and-spar-greenfields",
    "conversation": [{
      "invocation_id": "bhola-and-spar-greenfields",
      "user_content": {"role": "user", "parts": [{"text":
        "{\"response_number\": 1, \"response_id\": \"eval\", \"submitted_by\": \"pmushaya@lekkacredit.com\", \"submitted_at\": \"2026-03-06T12:40:10Z\", \"payable_to\": \"Bhola and spar greenfields\", \"amount\": 97.0, \"disbursed_on\": \"2026-03-04\", \"comment\": \"Office provisions\", \"files\": {\"signed_requisition_form\": [\"gs://ourfos-dev-attachments/evals/requisitions/bhola-and-spar-greenfields/signed_requisition_form/<sha256>\"], \"invoices\": [\"gs://…\"], \"receipts\": [\"gs://…\"]}}"}]},
      "final_response": {"role": "model", "parts": [{"text":
        "{\"approve\": true, \"reason\": \"why: two signed forms, stationery 20.01 and provisions 76.96, receipts 82.97 and 14.00. The form rounds to 97\", \"debit\": [{\"glCode\": \"5105\", \"amount\": 20.01}, {\"glCode\": \"5145\", \"amount\": 76.96}], \"credit\": [{\"glCode\": \"10000000\", \"amount\": 20.01}, {\"glCode\": \"10000000\", \"amount\": 76.96}]}"}]}
    }]
  }]
}
```

- `user_content` is the clean requisition as classify sends it, files as refs. The plugin swaps them for bytes, labelled by field, before the invocation starts
- `final_response` holds only what's scored, and the `why`

## The harness

- `services/evals/expenser/agent.py`: `app = App(root_agent=expenser's root_agent, plugins=[Attachments(), *expenser's plugins])`. `AgentEvaluator` runs a module's `App`, plugins and all, so Model Armor screens as in prod
- `Attachments`, a plugin, only in the eval module: `on_user_message_callback` reads the requisition from the first part, loads its files through `attachments.load`, and returns `turn(requisition, files)`. The same bytes, labels and order classify gives the model
- `services/evals/` is excluded from the image, like `tests/`

## The metrics

`services/evals/metrics.py`, ADK custom metrics, each 1 or 0 per invocation:

```json
{
  "criteria": {
    "no_false_approval":  {"threshold": 1.0},
    "accounts":           {"threshold": 1.0},
    "amounts":            {"threshold": 1.0},
    "no_false_rejection": {"threshold": 1.0}
  },
  "custom_metrics": {
    "no_false_approval":  {"code_config": {"name": "evals.metrics.no_false_approval"}},
    "accounts":           {"code_config": {"name": "evals.metrics.accounts"}},
    "amounts":            {"code_config": {"name": "evals.metrics.amounts"}},
    "no_false_rejection": {"code_config": {"name": "evals.metrics.no_false_rejection"}}
  }
}
```

- `no_false_approval`: approved what should be rejected. The dangerous one
- `accounts`: the same `glCode`s on each side. Lines are summed per account, so a split or a merge doesn't matter
- `amounts`: each account within a cent of the ledger's
  - **Rounded:** the total is the form's amount, and each account is within the gap between the form and the ledger (Bhola: 97 − 96.97). Passes, and is listed as rounded for me to look at
  - Anything else fails
- `no_false_rejection`: rejected what should be approved. Reported, not a safety fail
- `accounts` and `amounts` are not evaluated when either side rejects
- `glId` isn't scored: a unit test holds every `glCode` in the chart to its `glId`
- The harness writes ADK's results to a file and prints the rounded and failing cases from it, per metric

## Running

```
make evals ENV=dev                                   # pytest services/evals, every case 3 times
make evals ENV=dev CASE=bhola-and-spar-greenfields   # one case
```

- pytest, marked `eval`, so `make test` and CI never run it
- As me, with ADC: Vertex, Model Armor and the dev bucket
- 3 runs per case, to see Flash-Lite's variance
- Fails until every case passes. The per-metric failures are the hillclimb's list
- For a look rather than a gate: `adk eval services/evals/expenser services/evals/requisitions.evalset.json --config_file_path services/evals/test_config.json --print_detailed_results`, or `adk web` for one case's trace
- Cost: about 34 cases × 3 runs × 4 Model Armor screens, well inside the free 2M tokens a month. The model's tokens are cents

## The prompt

- Its two examples, City parking and Zimra (March), are eval cases too. They're swapped for synthetic ones that teach the same things, a parking expense and a PAYE liability, with other payees and amounts
- Nothing else changes before the baseline

## Fixtures

- Still the whole workflow: the trigger's cleaning, `simulate`'s failures, retries, handovers, fetch errors. `make smoke` and `make start`
- Evals score one step's judgement, with real files. Fixtures prove the plumbing around it
- `happy` stays on Drive, so smoke keeps covering Drive. `happy-gcs`, new, has the same files by `gs://`
- `nssa`, `bank` and `salary` go: they judged without files, and the evals now cover them with

## Terraform

- lekka-ourfos-infra: the bucket and its readers, in both projects
- lekka-ourfos: `ATTACHMENTS_BUCKET` on `ourfos-services`

## Bootstrapped, once

- The eval files, uploaded from expenser's inputs, each with its content type. The converting script writes the evalset's refs as it goes
- `happy`'s two files copied into `evals/requisitions/happy/` in dev, for `happy-gcs`

## Done when

- Both buckets exist, and `fetch(ref)` is deployed: `happy` and `happy-gcs` pass smoke on dev
- The eval files are up, and the evalset, metrics and harness are committed
- `make evals` runs end to end, and the baseline per metric is below
- Hillclimbing comes after, as its own commits, measured against the baseline. It isn't what done means

## What execution changed

-

## Not in this phase

- Hot to cold storage (Autoclass)
- A reused requisition: the hash in the object names is what it needs
- Reversing a requisition
- A judge for rejection reasons
- Evals in CI
- `check` and rounding: a model that posts the ledger's 96.97 for a form's 97 hands over in prod
