# Phase 7: evals

## Goal

- A number for how well expenser classifies real requisitions, and a way to raise it: hillclimb the prompt, one change at a time
- Most dangerous first: a false approval, a wrong amount, a wrong account. Each is a hard fail. A false rejection costs a handover, and is reported on its own
- Attachments get a home of their own: a GCS bucket per project, read through one `fetch(ref)` alongside Drive, ready for our own front end

## Shape

```
make evals ─▶ adk eval agents/expenser ─┐
form ─▶ trigger ─▶ workflow ─▶ classify ─┴─▶ expenser's App: the requisition, files as refs
                                               ├─ Attachments plugin: fetch(ref) ─┬─ bare id ─▶ Drive, as lekkai@
                                               │                                  └─ gs://    ─▶ the attachments bucket
                                               ├─ Model Armor: fields, whole prompt
                                               └─ the model: JSON + one part per file
make eval-failures ─▶ ADK's own results ─▶ which cases failed which metric
```

- The workflow, its steps and statuses are phase 6's. Where a file can come from changes, and the agent fetches it, not classify (ADR 3)

## Already on this branch

- The trigger wants `?workflow=requisition`: it picks the cleaner and the workflow, one webhook URL per form. A missing or unknown one is a 400. Smoke checks it
- `submitted_at` comes from the form's `created_at`, epoch milliseconds in UTC, not its zoneless `response_date`

## The attachments bucket

- `ourfos-dev-attachments` and `ourfos-prod-attachments`, in `africa-south1`. Made in lekka-ourfos-infra, like the sources bucket
- Uniform bucket-level access, public access prevention enforced, Google's default soft delete, no versioning: an object is named by its content, so it never changes
- Named by where it came from: `requisitions/<requisition id>/<field>/<sha256>`. Metadata repeats `source`, `id` and `field`. The content type is set on upload, never guessed from a name
- Evals live in dev only: `evals/requisitions/<case>/<field>/<sha256>`. Prod never holds test data
- Who reads, on the bucket, not the project: `ourfos-services` in both. I read it as the project's owner
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
- 36 cases:
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

## The agent fetches

- `agents/expenser/files.py`, the `Attachments` plugin, first in expenser's `App`: `on_user_message_callback` reads the requisition from the message, loads its files through `classify.attachments.load`, and returns `turn(requisition, files)`. Anything that isn't a requisition, like a question typed into `adk web`, is left alone
- classify sends the requisition alone. What a fetch raises comes out of ADK wrapped in a `RuntimeError`; classify re-raises the `HTTPException` inside, so its status still reaches the workflow
- `adk eval` runs this same agent, so the evals need no module of their own
- `services/evals/` is excluded from the image, like `tests/`

## The metrics

`services/evals/metrics.py`, ADK custom metrics, each 1 or 0 per invocation. A case passes a metric only at 1

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
  - **Rounded:** the total is the form's amount, and each account is within the gap between the form and the ledger (Bhola: 97 − 96.97). Passes
  - Anything else fails
- `no_false_rejection`: rejected what should be approved. Reported, not a safety fail
- `accounts` and `amounts` are not evaluated when either side rejects
- `glId` isn't scored: a unit test holds every `glCode` in the chart to its `glId`
- ADK keeps each run's results in `agents/expenser/.adk/eval_history/`. `services/evals/failures.py` reads which cases failed which metric; nothing is scored there

## Running

```
make evals                                  # every case once, then which failed which metric
make evals CASE=bhola-and-spar-greenfields  # one case, or several: CASE=a,b
make evals RUNS=3                           # three times over, to see Flash-Lite's variance
make evals CASE=zrp DETAIL=1                # with ADK's detailed tables
make eval-cases                             # the eval_ids CASE takes
make eval-failures RUNS=3                   # the failures of the last three runs again
```

- `adk eval agents/expenser services/evals/requisitions.evalset.json --config_file_path services/evals/test_config.json`, with `services/` on the path. It reads `agents/expenser/.env`, as `make agent` does: dev's model, Model Armor template and bucket
- By hand only (ADR 8), as me, with ADC: Vertex, Model Armor and the dev bucket
- ADK passes a run only if every case passes, so with ADR 11's known misses a full run exits non-zero. The list of failures is what to read
- ADK's `eval` extra is a dev dependency, never in the image
- `adk web` with a case's requisition pasted in shows one case's trace

## The prompt

- Its two examples, City parking and Zimra (March), are eval cases too. They're swapped for synthetic ones that teach the same things, a parking expense and a PAYE liability, with other payees and amounts

## Fixtures

- Still the whole workflow: the trigger's cleaning, `simulate`'s failures, retries, handovers, fetch errors. `make smoke` and `make start`
- Evals score one step's judgement, with real files. Fixtures prove the plumbing around it
- `happy` stays on Drive, so smoke keeps covering Drive. `happy-gcs`, new, is the Mr Muchenje eval case's requisition and files, by `gs://`

## Terraform

- lekka-ourfos-infra: the bucket and its readers, in both projects. The dev grants for the pipeline's evals, added first, came out again with ADR 8
- lekka-ourfos: `ATTACHMENTS_BUCKET` on `ourfos-services`

## Done when

- Both buckets exist, and `fetch(ref)` is deployed: `happy` and `happy-gcs` pass smoke on dev
- The eval files are up, and the evalset and metrics are committed
- `make evals` runs end to end, and the baseline per metric is below
- Hillclimbing comes after, as its own commits, measured against the baseline. It isn't what done means

## What execution changed

- 36 cases, not 34: Miss Jongwe is in both folders as the same Drive file, once a PDF and once a JPEG, so it's two type cases like Makora
- Rawson's ledger account, 1812 Investment property-Building, isn't in our chart of accounts, so the model can't post it. The case stays, and fails `accounts` until the chart has it
- Makururu's form links an invoice that isn't in expenser's inputs, so its case has the signed form only
- `ourfos-app-deployer`'s dev grants for the evals are in infra's Terraform, not by hand: `deployer-grantable-roles` already allows both roles
- `happy-gcs` is the Mr Muchenje eval case, by `gs://`, rather than copies of `happy`'s files: nobody but `ourfos-services` can read those as `lekkai@`
- `gcloud storage cp` reads `[1]` in a file name as a wildcard: the upload copied each file to a plain name first
- ADK's evals close each case's runner, and the Model Armor plugin closed its client with it: one app, so one client, for every runner. Cases running alongside were cancelled mid-call and recorded nothing, and later ones failed closed. The plugin now never closes it, as classify never did
- ADK's `eval` extra is needed to run evals at all: a dev dependency of services, so never in the image

### Baseline

36 cases × 3 runs, gemini-3.5-flash-lite, the prompt as lifted with its examples swapped. Locally, 4 minutes:

| Metric | Passed | Rate |
|---|---|---|
| `no_false_approval` | 108/108 | 100% |
| `no_false_rejection` | 105/108 | 97% |
| `accounts` | 93/99 | 94% |
| `amounts` | 93/99 | 94% |

- `rawson-real-estate` ×3: Legal Fees or Consultancy Fees. The ledger's account isn't in the chart
- `safeden-security-systems` ×3: Maintenance Equipment, where the ledger has Security Charges, for repairing a safe's dial
- `bhola-and-spar-greenfields` ×3, rejected: "two requisition forms are attached, but only one should be provided". The prompt's attachment rule, word for word from ourfos-v2
- Nothing rounded. Salaries and Salaries Fake were both rejected as salaries: Fake's mismatched attachment was never the reason

The dev pipeline's first run, as `ourfos-app-deployer`, 3 minutes: `no_false_approval` 108/108, `no_false_rejection` 108/108, `accounts` and `amounts` 94/102. Bhola was approved every time there, and split to the ledger's accounts once in three. The same prompt and model, so this is the variance three runs are there to show

## Not in this phase

- Hot to cold storage (Autoclass)
- A reused requisition: the hash in the object names is what it needs
- Reversing a requisition
- A judge for rejection reasons
- A scheduled eval run, for drift with no change of ours
- `check` and rounding: a model that posts the ledger's 96.97 for a form's 97 hands over in prod
