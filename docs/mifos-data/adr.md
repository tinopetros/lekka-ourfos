# Mifos data: decisions

Draft.

### 1. Mifos is read once, into a bucket of its own

- What's read from Mifos is kept in `gs://<project>-mifos`, and everything after reads the bucket: Firestore, a
  queryable copy, a UI. Never Mifos again for the same data
- Its own bucket, not attachments: attachments' lifecycle rules, when they come, mustn't reach it. 30-day soft delete
  and `prevent_destroy`, as attachments. In infra, lekka-ourfos-infra#26
- Not `services/sync.py`: that copies manual entries straight into Firestore. The bucket comes first; Firestore can be
  filled from it
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
- Clients and loans change: each fetch is a whole snapshot, `dt=<date>/`, and what changed is worked out by comparing
  snapshots

### 6. Only the latest client snapshot is kept, unless a client disappears

- Mifos deletes only pending clients, before activation; an active client can only be closed, and only once their
  loans are. So we assume no one deletes clients
- Each snapshot is compared with the last. No client gone: the new one replaces it. A client gone: the last snapshot
  that had them is kept, and the new one becomes the latest. Few snapshots, nothing lost
- `_perf.jsonl` records every fetch and its comparison, kept or not
- What's lost: a pending client created and deleted between two snapshots, who never had a loan
- 374 of ids 2–728 aren't listed today, in gaps of at most 14: consistent with pending clients deleted early on

### 7. Backfilled by hand, then nightly

- All of history once, by hand, a kind of data at a time, watched, and stopped at the first sign of strain (ADR 3)
- Then scheduled jobs each night, catching up on that day. Built once the backfill shows what Mifos can take
