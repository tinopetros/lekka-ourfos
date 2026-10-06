# Phase 12: mifos integration 2

## Goal

- A posted requisition can be corrected, as many times as needed: a reversal, then the corrected lines
- `journal_entries` is our record of manual journal entries, Lekkai's and people's in Mifos, from 1 Jan 2026, kept up to date each night
- Prod can be released without posting to Mifos

## Steps

1. **Phase 11's fixes**
   - The run's `posted` keeps Mifos's `transaction_date`, and its `created_on`
   - Comments: `Subject: {subject}. Response number: …. Workflow run: …`. The reference has its own field
   - `?mifos=false` on the trigger, kept on the run. Like a test run, it posts nothing and sends no third email
2. **`journal_entries/{transaction_id}`**, one per Mifos transaction
   - `transaction_date`, `created_on`, `office`, `currency`, `reference_number`, `comments`, `created_by`, `lines`, `entry_ids`
   - `source`: `lekkai` with its `form`, `submission` and `run`, or `mifos`
   - `status`: `live` or `reversed`, and `reverses` / `reversed_by`
   - Written in the step that posts. The read-back adds what only Mifos knows: `created_on`, `entry_ids`
3. **On the requisition's submission**: `live_entry`, and `journal_entries`, every post and reversal's transaction id in order
4. **The `correction` workflow**, its runs on the submission like the run that posted (`workflow: correction`)
   - Takes: `lines` (`debit`, `credit`), optional; `reason`; `requested_by`; `transaction_id`, optional, and if given must be `live_entry`
   - Refuses a requisition that was never posted, a stale transaction id, and unbalanced lines: the run ends `refused`, with no email
   - Claim `live_entry` → post its mirror, on its date → read back → post the corrected lines, on the same date → read back → reply in the thread
   - No lines: a reversal only
   - As post: never twice, never retried blind after a timeout. A claim whose mirror may have landed is never claimed again
   - Started through the Workflows API, as smoke does. A front end's route, behind its sign-in, comes later
5. **The correction's email**: a reply in the requisition's thread, to the same people. **CORRECTED**, the new entry's lines and the reason, or **REVERSED**, nothing re-posted, and the reason
6. **`/sync/journal_entries`**
   - Always manual entries only (`manualEntriesOnly=true`)
   - Each night: newest id first, back to the mark in `syncs/journal_entries` and 200 entries under it, since an entry mid-save can show after a higher id. Skips our Mifos user's, and transactions we hold
   - No mark: does nothing, and logs `journal_entries not preloaded`
   - `from=2026-01-01`: the preload. Everything from that transaction date, ours too: a transaction a run posted is `lekkai`, with its run
   - The mark only ever goes up, written in a transaction once the sync is done
7. **The schedule**: Cloud Scheduler starts the `sync` workflow, one job per entry in Terraform's `syncs`. `journal_entries`: `0 23 * * *`, `Africa/Harare`
8. **Prod**: planned, not released

## Smoke

Each run its own submission, so the corrections after know which to correct. Checked through each run's result: the deployer doesn't read Firestore

- `happy`: posted to `demo`, as before
- `mifos-off`: `?mifos=false`, done, `skipped: mifos`: nothing posted and no third email
- Corrections:
  - `correct-stale` on `happy`, a wrong transaction id: refused
  - `correct` on `happy`, to `demo` for real: done, with a reversal and a new transaction. Only possible if `happy` left a live entry
  - `reverse-only` on `happy-gcs`, stub: done, nothing re-posted
  - `correct-unposted` on `mifos-off`: refused
  - `correct-timeout` on `google-doc`, the mirror times out: handed over
- The sync: with no mark, `skipped: not preloaded`. With one, the mark after is never under the mark before

## By hand, once

- Dev, after the merge build's apply: the preload, `make sync FROM=2026-01-01`, and then a manual entry in `demo` as another user, for smoke to find
- Prod, after its release: the preload, when ready
- `make sync` and `gcloud scheduler jobs run` show the whole chain on dev

## Bootstrapped, once

- Infra enables `cloudscheduler.googleapis.com` (its PR)
- The deployer manages Scheduler's jobs, in both projects:

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  gcloud projects add-iam-policy-binding "$P" --condition=None \
    --member="serviceAccount:$SA" --role=roles/cloudscheduler.admin
done
```

## Before prod's release

- Prod's add-on URL carries `&mifos=false` until posting is ready
- Phase 11's: prod's requisition form asks for Reference Number, and `verify_ssl` once Mifos has a certificate
- Alerts on ERROR logs: `mifos post uncertain`, `not recorded`, a sync that failed

## Later

- Reversal mappings for 2026's manual entries, from a list
- A reversal workflow with no requisition, its runs on the journal entry
- The front end's routes, and their sign-in
