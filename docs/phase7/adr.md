# Phase 7: decisions and shortcuts

### 1. Attachments live in GCS, a bucket per project

- The attachments store for our own front end, not just a place for eval files. So prod gets one now too
- Named by where a file came from and by its content: `requisitions/<id>/<field>/<sha256>`. Browsable by source, and a reused file shows up as a hash already stored under another requisition
- Drive stays: the form still uploads there
- **Revisit** hot to cold storage (Autoclass), and whether Drive goes once the front end is live

### 2. One fetch, our bucket only

- A bare id is Drive, `gs://` is GCS. Every stored requisition stays valid, and the front end can post refs on day one
- Any other bucket is refused: refs will come from a client, and the services account can read more than attachments
- Prod reads the bucket for real, so `ourfos-services` reads it in both projects

### 3. Evals run inside ADK, not beside it

- `AgentEvaluator` runs our `App`, Model Armor included. A plugin in the eval module swaps refs for bytes through classify's own load and `turn()`, so the model sees what prod shows it
- The plugin lives only in the eval module. The deployed agent never fetches
- pytest over `AgentEvaluator`, as ADK's docs suggest for CI. `adk eval` and `adk web` read the same files for a closer look

### 4. Evals read GCS, not Drive

- Only `ourfos-services` can sign as `lekkai@` (phase 6 ADR 1). Letting me or a build sign too would widen what phase 6 accepted narrowly
- A bucket needs a reader grant, nothing more. Drive stays covered by smoke's `happy` and `file-missing`

### 5. Binary and deterministic

- Four custom metrics, no judge. A false approval, a wrong account or a wrong amount is a hard fail. A false rejection is reported on its own: it costs a handover, not money
- Accounts compare as sums per `glCode`, so splitting or lumping lines doesn't matter
- `glId` is a lookup, not a judgement: a unit test holds the chart to it
- **Revisit** with a judge for reasons, once the binary ones pass

### 6. The ledger's odd entries stand

- Parking as Advertising and Promotions, a valuation fee as Investment property. Parking depends on why the trip was made

### 7. No eval case in the prompt

- Two of the prompt's examples, City parking and Zimra (March), were eval cases. A score would count what the model was shown

### 8. On merge, at 0.70

- A step in the dev pipeline, after smoke and before prod's plan: every merge is scored against the model it just deployed, so a model or prompt change that drifts stops there
- Cloud Build, not GitHub: evals need Vertex, Model Armor and the bucket, and `make check` stays without GCP credentials. Pull requests don't run it; `make evals` does, by hand
- Passes when every metric's pass rate, across cases and runs, is at least 0.70. Low on purpose: nothing posts to Mifos yet, so a person still checks every run
- **Revisit** the bar as we see the baseline, and as posting gets real. A scheduled run, for drift with no change of ours, when it matters

### 9. Fixtures for plumbing, evals for judgement

- Fixtures drive the whole workflow and its failures, through the trigger. Evals score one step with real files
- `nssa`, `bank` and `salary` go: they judged without files, and handed over for it

### 10. Real people, private places

- The bucket holds real signatures, names and amounts: private, readers granted by name
- The evalset holds names and staff emails, as `happy` does. The repo is private and personal
- **Revisit** if the repo's audience grows
