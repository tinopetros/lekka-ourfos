# Phase 16: accounts from Mifos, then corrections

Notes, not yet a TDD. They assume mifos-connector-py has a release with `client.gl_accounts.list()` and `postable()`
(brief given to that repo on 2026-10-29).

## Where things stand

- Phase 15 reverses a requisition's live entry from its page: the correction workflow with no lines. It ends `reversed`
- The correction workflow already takes new lines, `{debit, credit}`, each `name`, `glCode`, `glId`, `amount`, and
  checks they balance. Nothing in the UI sends them yet
- Expenser picks accounts from `agents/expenser/accounts.csv`: 52 accounts, 42 expense, 6 asset, 4 liability, each
  with a Comment the model reads as a hint
- `/glaccounts` on `demo`, as the API's Mifos user: 161 accounts in 0.9s, 137 postable (detail, enabled, manual
  entries allowed). All 52 of the CSV's are among them. Prod's `default` tenant is still to check

## Next steps

1. **Accounts from Mifos.** Bump the connector's tag. Read the postable accounts, keep them a day, and fall back to the
   last read when Mifos is down, as names do on `users/{email}`. One place both the API and expenser read from
2. **Curated accounts, in an admin page.** Every postable account, with what helps the agent pick it: the Comment the
   CSV has now, editable, and whether it's offered at all. Which ones are most likely, e.g. how often each has been
   posted to. The CSV's 52 seed it, then it's edited here, not in the repo. Admins only, a new permission
   - May be overkill for now: fine to leave for later still, with the agent and corrections reading Mifos's accounts
     and the CSV's comments as they are
3. **The agent on live accounts.** Expenser reads the curated list instead of the CSV, so more accounts, maybe all
   postable expense, asset and liability ones, are open to it. Its glId and GL code stay lookups, never the model's to
   write. Evals and tests updated: more accounts must not make it worse on the cases it gets right now
4. **Corrections from the UI.** Beside Reverse journal entry, Correct journal entry: the live entry's lines to start
   from, an account picker on each line, add and remove lines, debits and credits totalled, and submit only when they
   balance. The picker searches by name or GL code, expenser's accounts first. The reverse endpoint takes optional
   lines: none reverses, some corrects. A run that corrects ends `corrected`

## Open questions

- Should the agent also see past journal entries, e.g. how similar requisitions were posted, or only the accounts?
- Who are admins: directors, tech, or a group of their own?
- Mifos changes nothing we hold until the sync runs again: a reversal or correction mirrors the entry as ourfos posted
  it. Say so in the dialogs until the sync is back
