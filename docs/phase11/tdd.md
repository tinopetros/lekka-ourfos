# Phase 11: mifos integration

## Goal

- An approved requisition is posted to Mifos as a journal entry. The last email shows what Mifos has, and its transaction id
- Dev first, posting to Mifos's `demo` tenant. Prod is wired for `default`, the books, but not released

## Steps

1. **The dependency.** [`mifos-connector`](https://github.com/tinopetros/mifos-connector-py) installs from its release tag, on my machine and in the image
2. **Settings and secrets.** The URL, tenant and office are tfvars. The username and password are Secret Manager, one pair per project, made by hand
3. **Connect.** Dev's service reads one GL account from `demo`: it reaches Mifos, and logs in
4. **Post.** The classified lines as one journal entry:
   - the run's id as its reference
   - dated the day it was disbursed, or today
   - never twice: a run that has posted returns its transaction
   - never on a test run
5. **Read back.** What Mifos has, compared with what we posted, line by line (ADR 2)
6. **The last email.** A reply in the thread: Mifos's lines and the transaction id (ADR 3)
7. **Prod.** Its tfvars and secrets, planned, not released

## Settings

- Defaults from the connector's own `.env`: the server's URL, office `1`
- Tenant: `demo` on dev, `default` on prod
- Currency: `USD`

## Smoke

- One fixture, `happy`, posts to `demo` for real on every dev build
- Every other fixture that reaches `post` keeps the stub

## Open

- How Actions and Cloud Build get read access to the private connector
- Mifos's certificate: self-signed, expired, on a bare IP. Prod can't verify it
