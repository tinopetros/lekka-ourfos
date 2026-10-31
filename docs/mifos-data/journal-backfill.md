# Manual journal entries: the backfill

Every manual journal entry in prod Mifos's `default` tenant, read a range at a time on Oct 31 2026 and kept in
`gs://ourfos-prod-mifos/manual_journal_entries/`, one file a range (ADRs 4 and 5). Each range's timing is in that
folder's `_perf.jsonl`.

- **64 files, 2,852 transactions, 5,982 lines**, April 2022 to October 2026 (October still open)
- Every read one page. All but one answered in 2.7–4.1s; the week of 26 Jan 2026 took 21.3s
- Mifos cut one read off (April 2026), read in 2.8s minutes later; one week timed out at 65s on the first run (16 Feb
  2026) and read in 2.9s an hour later
- Weeks from 29 Dec 2025 to 15 Feb 2026, as the first run went; 16 Feb–15 Mar and 16–31 Mar round onto calendar
  months, which every other file is

## Transactions per month

```mermaid
xychart-beta
    title "Manual journal transactions per month, Jan 2022 to Oct 2026"
    x-axis ["22-01", "22-02", "22-03", "22-04", "22-05", "22-06", "22-07", "22-08", "22-09", "22-10", "22-11", "22-12", "23-01", "23-02", "23-03", "23-04", "23-05", "23-06", "23-07", "23-08", "23-09", "23-10", "23-11", "23-12", "24-01", "24-02", "24-03", "24-04", "24-05", "24-06", "24-07", "24-08", "24-09", "24-10", "24-11", "24-12", "25-01", "25-02", "25-03", "25-04", "25-05", "25-06", "25-07", "25-08", "25-09", "25-10", "25-11", "25-12", "26-01", "26-02", "26-03", "26-04", "26-05", "26-06", "26-07", "26-08", "26-09", "26-10"]
    y-axis "Transactions" 0 --> 180
    bar [0, 0, 0, 4, 0, 0, 0, 0, 0, 16, 15, 6, 8, 7, 81, 18, 11, 12, 18, 21, 15, 30, 25, 90, 29, 28, 36, 37, 26, 46, 49, 48, 52, 87, 72, 114, 144, 108, 113, 80, 101, 112, 164, 119, 91, 92, 104, 98, 53, 86, 24, 53, 63, 57, 55, 41, 48, 45]
```

Early 2026's weeks are added into the month they start in.

## Seconds per read

```mermaid
xychart-beta
    title "Seconds per read, in date order (60s stops a run)"
    x-axis ["22-01", "22-02", "22-03", "22-04", "22-05", "22-06", "22-07", "22-08", "22-09", "22-10", "22-11", "22-12", "23-01", "23-02", "23-03", "23-04", "23-05", "23-06", "23-07", "23-08", "23-09", "23-10", "23-11", "23-12", "24-01", "24-02", "24-03", "24-04", "24-05", "24-06", "24-07", "24-08", "24-09", "24-10", "24-11", "24-12", "25-01", "25-02", "25-03", "25-04", "25-05", "25-06", "25-07", "25-08", "25-09", "25-10", "25-11", "25-12", "25-12", "26-01", "26-01", "26-01", "26-01", "26-02", "26-02", "26-02", "26-03", "26-04", "26-05", "26-06", "26-07", "26-08", "26-09", "26-10"]
    y-axis "Seconds" 0 --> 60
    line [4.12, 2.73, 2.95, 2.75, 2.72, 2.75, 2.76, 2.84, 2.74, 2.83, 2.83, 2.75, 2.98, 2.81, 2.84, 2.86, 2.81, 2.81, 2.73, 2.73, 2.82, 2.74, 2.81, 2.86, 2.75, 2.91, 2.86, 2.82, 2.82, 2.77, 2.81, 2.74, 2.80, 2.95, 2.75, 2.76, 2.82, 2.78, 2.83, 2.72, 2.83, 2.89, 2.84, 2.80, 2.80, 2.83, 2.75, 2.76, 2.79, 2.76, 2.81, 2.82, 21.31, 2.73, 2.80, 2.87, 2.77, 2.77, 2.83, 2.73, 2.83, 2.75, 2.83, 2.79]
```

## By year

| Year | Transactions | Lines | Empty months | Reads | Booked by (months active) |
|---|---:|---:|---:|---|---|
| 2022 | 41 | 87 | 8 | 2.72–4.12s | dgoto\* 4, smataruka\* 2, AMasvaure 1, admin 1 |
| 2023 | 336 | 822 | 0 | 2.73–2.98s | dgoto\* 10, AMasvaure 7, admin 5, smataruka\* 4, ZSaruchera 2, KMbinda\* 2 |
| 2024 | 624 | 1,357 | 0 | 2.74–2.95s | ZSaruchera 10, AMasvaure 8, LTanga 6, smataruka\* 5, KMbinda\* 4, LGovera\* 2, RPanyangara 1 |
| 2025 | 1,326 | 2,653 | 0 | 2.72–2.89s | ZSaruchera 13 |
| 2026 | 525 | 1,063 | 0 | 2.73–21.31s | ZSaruchera 15, lekkai@lekkacredit.com 3, TPSuperUser 2 |

\* Mifos users since deleted; Mifos keeps their entries under `<n>_DELETED_<name>`. Years go by each file's first day,
so 29–31 Dec 2025 count in 2025.

## Worth a look

- April 2022 has 4 entries, six months before the first client was activated (28 Oct 2022); none Jan–Mar or May–Sep
  2022. 2021 may hold setup entries too, unread
- Bookkeeping passed from dgoto (2022–23) to AMasvaure (2023–24) to ZSaruchera (2024 on). `admin` booked entries in
  2022 and 2023
- lekkai@ booked 3 entries in April 2026 and 2 in May, before ourfos posted real requisitions from 29 Oct; TPSuperUser
  3 and 2 in the same months
- 2025 is the busiest year, 1,300 transactions; July 2025 the busiest month, 164
