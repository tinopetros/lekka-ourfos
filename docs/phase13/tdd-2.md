# Phase 13, part 2: establish-fe-2

## Goal

- The UI from part 1, laid out to last: a home page, records on pages of their own, a sidebar that gets out of the way
- Still read only. Create buttons are there, and say they're coming

## Steps

1. **A record is a page**, not a sheet: `/forms/{form}/{id}`, `/journal/{transaction_id}`
   - A breadcrumb back to its list, on the page of the list you came from
   - Previous and next, ← and →, through the list's rows, into its next page when one runs out
   - Two tabs. **Overview**: where it stands, its answers, then its live entry's lines. **History**: its runs, oldest first, as a timeline, each posting's lines inline
   - Files open in a modal: Drive's own preview, which only shows what your Google account can open; ours in GCS through the API, which streams them behind IAP
2. **A row peeks on hover**: after the pointer rests on it, a card with its subject, amount and where it stands. It starts loading the record's page, so a click is quick
3. **The sidebar**: shadcn's, collapsible to icons with a button
   - **Workflows**: Requisitions, Vehicle logs, Loan approvals, Write-offs. **Accounts**: Journal entries. Headings give way to lines when collapsed
   - Collapses on a record's page, unless you've pinned it open. Remembered in the browser
   - Every icon has a tooltip. The build at its foot, as the commit
4. **Home**: a greeting, a search bar scoped to one kind of record (a look only, for now), and a card for each list, with a way straight to creating one
5. **Create** on every list: a stub, for now
6. **Hi, then your name**: the start of your email until Workspace's directory gives us names
7. **Skeletons**, shaped like what's coming, instead of a spinner
8. **More contrast** on hover
9. **Each form's title** is its own, not made from its noun: Loan approvals, Write-offs

## Bootstrapped, once

- Infra: `ourfos-api@` reads the attachments bucket, for the file modal
