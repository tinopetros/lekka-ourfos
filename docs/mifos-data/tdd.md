# Mifos data

Draft. A copy of everything that matters in Mifos, kept by us: first archived in a bucket, later a live copy that
ourfos and people can read without going near Mifos.

Mifos's API reference: https://demo.mifos.io/api-docs/apiLive.htm

## Why

Mifos is our core banking system, and it hasn't served us well. Some of that is malfunction; most of it is
misconfiguration. A copy of its data is the foundation for each of these:

1. **Investigating what went wrong.** We can't yet even begin to look into problems we know about, e.g. early loan
   closures accounted for incorrectly, again and again. That takes every loan, its transactions and the journal entries
   they booked, side by side, over all of history, and Mifos's own screens and API are too slow to query that way
2. **A UI for people investigating.** Loans, their transactions and the books in one place, quick to search and compare
3. **ourfos itself.** Features that need clients, loans or the books read our copy, not Mifos
4. **Leaving Mifos.** A migration to our own, opinionated implementation in ourfos, should we go that way, starts from
   a complete copy of what Mifos holds

For now the goal is only the foundation: fetchers that archive Mifos's data in a bucket, by hand at first, then on a
schedule. What reads the bucket comes later.

## What's copied

- **Clients**
- **Loans**: the loans those clients took
- **Loan transactions**: disbursements, repayments, charges, waivers, write-offs and closures on those loans
- **Their journal entries**: what each loan transaction booked in the books
- **Manual journal entries**: entered by hand, largely expenses. Kept apart from the loans' own (ADR 4)
- **Configuration**: loan products, the chart of accounts, and the rest of how Mifos is set up to book, since
  misconfiguration is where most of our problems started

Fetched through the relationships between them where we can, a loan's transactions through its loan, so each record
carries its loan and client.

## How

1. **A backfill through all of history.** By hand, one kind of data at a time, slowly enough for Mifos, which is
   easily overwhelmed (ADR 3). Lekka's data starts no earlier than 2020, likely 2022: the oldest client was activated
   on 28 Oct 2022
2. **Then nightly, incremental.** Scheduled jobs that catch up overnight on what changed that day, so the copy is never
   more than a day behind, and a failed night is caught up the next
3. **Then whatever reads it.** Cleaning, a queryable copy (e.g. BigQuery over the bucket), and the uses above

Implementation is worked out as we go.

## Where it stands

- `gs://ourfos-prod-mifos` and `ourfos-dev-mifos`, lekka-ourfos-infra#26, infra 0.26.0 (ADR 1)
- Manual journal entries, all of 2026, Oct 31: 16 ranges, 551 transactions, 1,115 lines, 29 Dec 2025 to 31 Oct 2026
  (October still open). Every read one page, 2.7–2.9s, but for one week at 21s, a week that timed out at 65s and
  read in 2.9s an hour later, and April cut off once and read in 2.8s minutes after. ZSaruchera booked nearly all;
  lekkai@ 3 in April, 2 in May and 14 in October; TPSuperUser 3 in April and 2 in May
- Manual journal entries, 2022–2025, Oct 31, a year a run: 2025 1,300 transactions, 2024 624, 2023 336, 2022 41.
  48 months, every read one page, 2.7–4.1s, no cut-offs. Nothing from Jan to Mar 2022, 4 in April 2022 (six months
  before the first client), then none until October. In all: 64 files, 2,852 transactions, 5,982 lines. Charts and stats: [journal-backfill.md](journal-backfill.md)
- Clients, Oct 31: 353 (352 active, 1 closed) across Head Office, Belvedere, Kadoma and Marondera. 2 pages, about 1s
  each. First snapshot, `latest/` and the change log, as ADR 6. Nightly from #55, once released
- Loans, Oct 31: 1,379, without associations, 7 pages of 1.2–1.4s, 6.2 MB. Kept as clients are, nightly from #55. A loan read with
  `associations=all` had Mifos drop the connection: transactions and schedules come later, an association at a time

## Open

- Loans: how often to snapshot closed ones, which seldom change, and how to notice one that did
- Loan transactions and their journal entries: per loan (about 1,400 reads a full pass), or the loans' journal entries
  by week and joined to loans after
- A read-only Mifos user for the fetchers. Until then they read as prod's Mifos user, read only
- Clients are personal data: who can read the bucket, and how a deletion request reaches it
- Whether whoever hosts Mifos can give us a database dump or a read replica instead, at no load on Mifos
- Where the fetchers run, once scheduled
