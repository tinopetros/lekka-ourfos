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

### 3. Evals are ADK's own, and the agent fetches its files

- `make evals` is `adk eval` on the deployed agent, `agents/expenser`, unchanged: no second agent module, no runner of ours. Custom metrics are ADK's `code_config`, and the results are the ones ADK keeps. `make eval-failures` only reads them
- So the agent fetches its own files: a plugin, before Model Armor, turns the requisition's refs into the turn classify used to build. classify, `adk eval` and `adk web` all hand the agent the same thing, the requisition
- This reverses phase 6's classify-fetches. The agent now imports services' fetch code; they ship side by side in one image and one environment
- ADK wraps a plugin's exception in a `RuntimeError`. classify unwraps a fetch's `HTTPException`, so the workflow still retries or hands over on its status. A test holds ADK to that
- Drive refs only fetch on Cloud Run, as `ourfos-services`. Locally, `adk web` and `adk eval` read `gs://` refs only

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

### 8. By hand, not in CI

- A run of every case costs about 20 cents, more than a month of the application's own model use. Run before and after a prompt or model change, not on every merge
- ADK passes a run only when every case passes, so with ADR 11's known misses a full run fails. Read which cases failed which metric, not the exit code
- The first baseline was 92% or better on every metric, and no false approval in 108 case runs: that's the level to hold
- **Revisit** once posts to Mifos are real, and a drifting model costs more than a run: in CI, or on a schedule

### 9. Fixtures for plumbing, evals for judgement

- Fixtures drive the whole workflow and its failures, through the trigger. Evals score one step with real files
- `nssa`, `bank` and `salary` go: they judged without files, and handed over for it

### 10. Real people, private places

- The bucket holds real signatures, names and amounts: private, readers granted by name
- The evalset holds names and staff emails, as `happy` does. The repo is private and personal
- **Revisit** if the repo's audience grows

### 11. Known misses, until Mifos

The baseline's failures, accepted for now: most cases pass, and these matter once posts are real. **Revisit** all of them when Mifos comes in

- **Rawson: an account the chart doesn't have.** The ledger booked a valuation fee to 1812, Investment property-Building, which isn't in `accounts.csv`, so the model can't choose it. Even with it there, a valuation fee could fairly go either way. There will always be cases like this. Check Mifos's chart for new or changed accounts regularly, and add them to `accounts.csv`
- **Bhola: two requisitions on one submission.** The prompt, from ourfos-v2, allows one requisition form per submission, so the model rejects or splits Bhola's two unpredictably. Our own front end should enforce one per submission, so it never reaches the model
- **Safeden: a judgement call.** Repairing a safe's dial goes to Maintenance Equipment every time; the ledger has Security Charges. Both are defensible. Leave it to the prompt's account comments, if at all
- **Salaries Fake: rejected for the wrong reason.** It's rejected as a salary, never because its attachment is Mr saruchera's requisition, not a payroll. A good place to hillclimb whether the model checks the attachment against the form
