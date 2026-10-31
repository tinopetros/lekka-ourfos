# Mifos data: decisions

Draft.

### 1. Mifos is read once, into a bucket of its own

- What's read from Mifos is kept in `gs://<project>-mifos`, and everything after reads the bucket: Firestore, a
  queryable copy, a UI. Never Mifos again for the same data
- Its own bucket, not attachments: attachments' lifecycle rules, when they come, mustn't reach it. 30-day soft delete
  and `prevent_destroy`, as attachments. In infra, lekka-ourfos-infra#26
- Not `services/sync.py`, now deprecated (ADR 8)
- Changes phase 12 ADR 7: not one preload request since 1 Jan 2026, but a week at a time. Narrows phase 12 ADR 11:
  Mifos can be read after all, once, narrowly and slowly

### 2. Kept as Mifos sends it, in folders BigQuery reads as partitions

- Each record as Mifos's API answered it, plus `_fetched_at`. No cleaning or reshaping on the way in: that's
  downstream, and can be redone from the raw copy
- JSONL, in `name=value` folders (`week=2026-01-05/`, `dt=2026-10-31/`), so BigQuery can read the bucket as a
  partitioned external table as it is
- Each kind of data keeps a `_perf.jsonl` beside it: every fetch's timing and counts, whether or not it stored anything

### 3. Mifos is protected over speed

- One read at a time, 15s apart, never retried. A read over 60s stops the run: Mifos slows in spells, and retrying
  into one made it worse before (phase 12 ADR 11)
- Always narrow: a week of journal entries, a page of 200 of a list
- Paged until a page comes back short, never by `totalFilteredRecords`: it said 1 for a week of 25 lines
- Restarted by hand after a stop, from where it stopped, not straight away

### 4. Manual journal entries are their own data, apart from the loans'

- `manual_journal_entries/`, `manualEntriesOnly=true`: what people book by hand, largely expenses, and ourfos's own
  posts. The name says manual so it's never mistaken for the whole journal
- The entries loans book for themselves are fetched with their loan transactions, so each joins to its loan and client

### 5. Events by week, things by snapshot

- Journal entries don't change once booked: one file a Monday–Sunday week, by transaction date. A week fetched again
  is rewritten whole, so a re-fetch is safe and catches entries booked late with past dates
- Clients and loans change: each fetch is the whole list, compared with the one before (ADR 6)

### 6. Clients and loans: the first snapshot, the latest, and a log of what changed

- Kept: `dt=<date>/`, the first snapshot, never rewritten; `latest/`, replaced by each fetch; and `_changes.jsonl`,
  a line for each client or loan that's new, changed or gone, with the date. Not a snapshot a day: storage stays at
  two copies and a log of kilobytes, and any day's list can be rebuilt from the first and the changes after it
- A change is a field someone moves: status, dates, people (loan officer, staff, office), amounts disbursed, repaid,
  waived or written off, charges, contact details. The line keeps each field's old and new value
- Not a change: what the calendar moves on its own, overdue amounts, days in arrears, overdue since, NPA and
  delinquency. Every active loan moves on those each night, which would drown the rest. They're still in `latest/`
- A client or loan gone keeps its last whole record on its line. Mifos deletes only pending clients and loans not yet
  approved, so we assume none are, but a disappearance costs nothing to keep
- What's expected to change: the active loans (90 on Oct 31) and new applications, now and then a client's details.
  A closed or rejected loan that changes is a finding, e.g. a reversal that reopened it; overpaid and written-off ones
  can change for real, a refund or a recovery
- `_perf.jsonl` records every fetch, its timings and how many were new, changed or gone
- Once loans' transactions and schedules are fetched, past balances come from them too; the log stays the record of
  what the lists said
- What's lost: anything created and deleted between two fetches, which never had a loan or a transaction
- Gaps in the ids: 374 of clients' 2–728 and 172 of loans' 1–1,551 aren't listed on Oct 31, consistent with
  applications deleted before activation or approval

### 7. Backfilled by hand, then nightly

- All of history once, by hand, a kind of data at a time, watched, and stopped at the first sign of strain (ADR 3)
- Then scheduled jobs each night, catching up on that day. Built once the backfill shows what Mifos can take

### 8. The sync into Firestore is deprecated

- Phase 12's `/sync/journal_entries` (`services/sync.py`) copied manual entries from Mifos straight into Firestore, each
  night from a mark. Built, never scheduled, never preloaded on prod
- Deprecated: Mifos is read into the bucket (ADR 1), and Firestore's `journal_entries`, when it holds people's entries,
  is filled from the bucket. Nothing new is built on the sync
- Its code, the `sync` workflow and Terraform's empty `syncs` stay until something replaces them, then go together
- Closes phase 12 ADRs 6 and 7
