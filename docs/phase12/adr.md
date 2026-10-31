# Phase 12: decisions and shortcuts

### 1. A reversal is a mirror image, not Fineract's reversal

- Fineract's `command=reverse` doesn't work on our server
- So a reversal is a new manual entry, every debit a credit and every credit a debit
- Mifos sees two live entries. Only our record links them

### 2. A correction is a reversal and a new post, both on the original's date

- So the period it was booked in always balances
- With no lines, it's a reversal only
- A reversal is never reversed: to undo one, correct again

### 3. Corrections are a workflow

- For uniformity, and for an approval step later, e.g. when a loan officer asks
- Its runs are on the submission, beside the run that posted (phase 10 ADR 1)
- A reversal with no requisition, later, gets its own workflow, its runs on the journal entry

### 4. The live entry is kept on the requisition, and a mirror that may have landed blocks it

- One place to look for what a correction reverses. A front end's transaction id only confirms it
- Before posting a mirror, the run writes `reversing` on the original. If the post timed out, it may have landed, so that entry is refused to every correction, this run's too, until a person has checked Mifos and either recorded the mirror or cleared it. A post that certainly didn't land clears it
- Not taken: **a claim on the requisition, in a transaction**, with rules for whichever run held it. It also stopped two corrections started at once, which is unlikely with one accountant starting them by hand
- The cost: two corrections started within a second of each other could both pass the first check, and the second would be refused only at its mirror

### 5. Links are never inferred

- A reversal is linked only when Lekkai made it, or when you list it
- Not from comments: anyone can write them

### 6. The sync only adds

- Entries are taken as immutable, so it never reconciles ours with Mifos's
- Manual entries only, and within the preload's dates. Fineract can't filter by created date, so it pages by entry id, newest first, back to a mark. The date range is there to keep Mifos's query small: by transaction date, it can't say what's new
- 10 entries under the mark again each night, a buffer: Mifos numbers an entry when it starts saving it, so a slow one can show after a higher id
- Our Mifos user's entries are skipped: the step that posts records them. So that user is Lekkai's alone, never a person's in Mifos's screens
- **Closed** by [Mifos data ADR 8](../mifos-data/adr.md): the sync is deprecated. Mifos's data is archived in a bucket first, and Firestore filled from there

### 7. The preload is the sync from 1 Jan 2026

- The same route and code, so it needs no prod credentials on a laptop
- By hand, on each env, never in a build
- **Closed** by [Mifos data ADRs 1 and 8](../mifos-data/adr.md): manual entries are fetched a week at a time into a bucket, not preloaded into Firestore

### 8. `mifos=false` is per request, like `test`

- Prod can be released with posting off, and turned on without a deploy
- **Closed** by phase 15 ADR 6: prod posts, and with the Google Forms closed, no link carries `mifos=false`

### 9. Scheduler runs as `ourfos-trigger`

- It already starts workflows, and the deployer already acts as it
- Not taken: **an account of its own**. An infra change and a grant, for the same role
- The cost: whatever runs as it can start any of our workflows, as the trigger already can
- **Closed** by phase 15 ADR 7: the trigger is retired, and the jobs run as `ourfos-api`, which already starts workflows

### 10. Scheduler's jobs are in europe-west1

- Cloud Scheduler isn't offered in africa-south1, nor anywhere in Africa
- A job holds only its schedule and the call that starts the workflow, which still runs in africa-south1. No data is in it
- Its time zone is still Africa/Harare

### 11. Mifos is written to, not read

- Mifos's reads of journal entries take minutes: its own screens took 5 for one day's manual entries, and 2.9 for one transaction id. Writes still answer in seconds
- So nothing reads it back: a post's proof is the transaction id Mifos answers with. The run, the record and the last email keep what we sent. The cost: a line booked differently from what we sent goes unseen, unlikely since Mifos books what it's sent or refuses it
- So `journal_entries` holds only what we post. The sync is built and paused: no schedule, no preload. ADRs 6, 7 and 9 wait for it
- The start-up check reads our office instead
- A post that times out still hands over, and finding it in Mifos by its workflow run is now a search of minutes
- Closes phase 11 ADRs 2 and 3
- **Narrowed** by [Mifos data ADR 1](../mifos-data/adr.md): Mifos is read after all, once, narrowly and slowly, into a bucket. Posts still aren't read back
