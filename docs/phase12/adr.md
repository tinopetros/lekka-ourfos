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

### 4. The live entry is kept on the requisition

- One place to look, claimed in one transaction, so two corrections can't both reverse it
- A claim stands until its run ends without having tried the mirror. One that tried and didn't hear back stands for good: a person checks Mifos
- A front end's transaction id only confirms it

### 5. Links are never inferred

- A reversal is linked only when Lekkai made it, or when you list it
- Not from comments: anyone can write them

### 6. The sync only adds

- Entries are taken as immutable, so it never reconciles ours with Mifos's
- Manual entries only. Fineract can't filter by created date, so it pages by entry id, newest first, back to a mark
- 200 entries under the mark again each night: Mifos numbers an entry when it starts saving it, so a slow one can show after a higher id
- Our Mifos user's entries are skipped: the step that posts records them. So that user is Lekkai's alone, never a person's in Mifos's screens

### 7. The preload is the sync from 1 Jan 2026

- The same route and code, so it needs no prod credentials on a laptop
- By hand, on each env, never in a build

### 8. `mifos=false` is per request, like `test`

- Prod can be released with posting off, and turned on without a deploy

### 9. Scheduler runs as `ourfos-trigger`

- It already starts workflows, and the deployer already acts as it
- Not taken: **an account of its own**. An infra change and a grant, for the same role
- The cost: whatever runs as it can start any of our workflows, as the trigger already can
