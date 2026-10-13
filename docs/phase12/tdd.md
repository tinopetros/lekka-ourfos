# Phase 12: mifos integration 2

## Goal

- A posted requisition can be corrected, as many times as needed: a reversal, then the corrected lines
- `journal_entries` is our record of the journal entries we post. People's in Mifos, by a sync, wait until Mifos's reads are usable (ADR 11)
- Prod can be released without posting to Mifos

## Steps

1. **Phase 11's fixes**
   - The run's `posted` keeps the `transaction_date` we posted on, and `created_on`, the day we posted it
   - Comments: `Subject: {subject}. Response number: …. Workflow run: …`. The reference has its own field
   - `?mifos=false` on the trigger, kept on the run. Like a test run, it posts nothing and sends no third email
2. **`journal_entries/{transaction_id}`**, one per Mifos transaction
   - `transaction_date`, `created_on`, `office`, `currency`, `reference_number`, `comments`, `lines`: what we sent, and Mifos's transaction id. A synced one would also have `created_by` and `entry_ids`
   - `source`: `ourfos`, made through ourfos, or `mifos`, made in Mifos's own screens and brought in by the sync
   - `by`, on ours: `lekkai` for the expense workflow's posts, or who asked for a correction. A workflow's also have `form`, `submission` and `run`. Mifos's say who in `created_by`
   - Three fields for reversals: `status`, `live` or `reversed`; `reverses`, on a mirror, naming what it reverses; `reversed_by`, on a reversed entry, naming its mirror
   - Written in the step that posts. Never read back from Mifos (ADR 11)
3. **On the requisition's submission**: `live_entry`, and `journal_entries`, every post and reversal's transaction id in order
4. **The `correction` workflow**, its runs on the submission like the run that posted (`workflow: correction`)
   - Takes: `lines` (`debit`, `credit`), optional; `reason`; `requested_by`; `transaction_id`, optional, and if given must be `live_entry`
   - Refuses a requisition that was never posted, a stale transaction id, and unbalanced lines: the run ends `refused`, with no email
   - Check `live_entry` → mark it `reversing` → post its mirror, on its date → post the corrected lines, on the same date → reply in the thread
   - No lines: a reversal only
   - As post: never twice, never retried blind after a timeout. An entry whose mirror may have landed is refused until a person has checked Mifos (ADR 4)
   - Started through the Workflows API, as smoke does. A front end's route, behind its sign-in, comes later
5. **The correction's email**: a reply in the requisition's thread, to the same people. **CORRECTED**, the new entry's lines and the reason, or **REVERSED**, nothing re-posted, and the reason
6. **`/sync/journal_entries`**, built and paused: no schedule, no preload, not in smoke (ADR 11)
   - Always manual entries only (`manualEntriesOnly=true`), and always a date range: Mifos has hundreds of thousands of entries, most of them loans' and savings'
   - Each night: newest id first, back to the mark in `syncs/journal_entries` and 10 entries under it, since an entry mid-save can show after a higher id. Skips our Mifos user's, and transactions we hold
   - No mark: does nothing, and logs `journal_entries not preloaded`
   - `from=2026-01-01`: the preload. Everything from that transaction date, ours too: a transaction a run posted is `ourfos`, by `lekkai`, with its run
   - The mark only ever goes up, written in a transaction once the sync is done. The preload also keeps its `from` on it: each night reads within that window, so an entry booked back anywhere in it is still found
7. **The schedule**: Cloud Scheduler starts the `sync` workflow, one job per entry in Terraform's `syncs`. None for now. `journal_entries` would be `0 23 * * *`, `Africa/Harare`
8. **No read-back** (ADR 11): the expense and correction workflows go from post to email. The email shows what we posted and Mifos's transaction id. The start-up check reads our office, not journal entries

## Smoke

Each run its own submission, so the corrections after know which to correct. Each run's result, then what they wrote, read from dev's Firestore by `scripts/smoke_checks.py` (the deployer reads dev's database: infra #19)

- `happy`: posted to `demo`, as before
- `mifos-off`: `?mifos=false`, done, `skipped: mifos`: nothing posted and no third email
- Corrections:
  - `correct-stale` on `happy`, a wrong transaction id: refused
  - `correct` on `happy`, to `demo` for real: done, with a reversal and a new transaction. Only possible if `happy` left a live entry
  - `reverse-only` on `happy-gcs`, stub: done, nothing re-posted
  - `correct-unposted` on `mifos-off`: refused
  - `correct-timeout` on `google-doc`, the mirror times out: handed over
- In Firestore: `happy`'s entry is ours by `lekkai`, `Subject:`, with its dates and the lines we sent; it reads posted, reversed, posted, the correction's entries by who asked; the mirror swaps every line on the original's date; `happy-gcs` has nothing live; `mifos-off` has no entries, no third email, and its status still `done`

## By hand, once

- Dev: people's entries from Mifos dropped from `journal_entries`, with the sync's mark, so dev holds only what we posted, as prod will

## Bootstrapped, once

- Infra enables `cloudscheduler.googleapis.com` (its PR)
- The deployer manages Scheduler's jobs, in both projects. Run on Oct 6:

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  gcloud projects add-iam-policy-binding "$P" --condition=None \
    --member="serviceAccount:$SA" --role=roles/cloudscheduler.admin
done
```

## Before prod's release

- Prod's add-on URL carries `&mifos=false` until posting is ready

## Later

- The sync and a preload, once Mifos's reads are usable: one page a call, a longer timeout for lists only, never retried after a timeout, and a narrow window each night (the cost follows the window, not what's new)
- Mifos's read-back, if its reads ever answer in seconds

- Reversal mappings for 2026's manual entries, from a list
- A reversal workflow with no requisition, its runs on the journal entry
- The front end's routes, and their sign-in

## What execution changed

- Fineract sorts `/journalentries` by `id`, both ways, but its `totalFilteredRecords` says 1 whatever the count: the sync pages until a short page
- `demo` has 431 manual transactions in 2026, 862 lines, read in 6 seconds: the preload is one call, no cursor
- The deployer didn't read Firestore (infra #16 dropped its grant). Smoke checked each run's result first, then infra #19 let it read dev's, so smoke checks what was written too
- Those checks found a refused correction left its requisition's status `received`: a correction's run now has no status until it posts or ends
- A test run before the record was faked wrote `L42` to dev's Firestore through a laptop's credentials. Tests now can't reach Firestore at all (`tests/conftest.py`)
- Correction fixtures are under `requisition/corrections/`: a folder of `fixtures/` is a form, to the trigger's tests
- This branch on dev, without the Scheduler job: smoke passed, and `smoke-happy-1791320954561042000` reads posted, reversed, posted, each entry with Mifos's ids. Then the preload, by hand: 428 added, the 3 the correction had recorded skipped, and a nightly sync after it, 0 added, the mark unmoved
- Dev's record also holds the stub's entries, `stub-txn-…`, from fixtures. Prod never simulates, so never has them
- 9 of Lekkai's posts in `demo` match no run in dev's Firestore, so they're `ourfos`, by `lekkai`, with no run. Why those runs are missing isn't checked yet
- Mifos's `demo` stopped answering journal-entry reads for a day, even `limit=1`, while `/offices` still answered. The nightly sync and the start-up check were reading with no date range, and so were the checks while it was down. Now every read is manual only and in a range, `manual_entries` refuses one without, and the start-up check reads only today's
- Then Mifos's own screens: 5 minutes for one day's manual entries, 2.9 minutes for one transaction id. A post still answered in 2.3 seconds. So no read-back and no sync for now (ADR 11). Each list read we gave up on at 15s likely kept running in Mifos, and each retry started another
