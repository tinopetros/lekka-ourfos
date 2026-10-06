# Phase 11: mifos integration

## Goal

- An approved requisition is posted to Mifos as a journal entry. The last email shows what Mifos has, and its transaction id
- Dev first, posting to Mifos's `demo` tenant. Prod is wired for `default`, but not released until there is a reversal / remediation plan

## Steps

1. **The dependency.** [`mifos-connector`](https://github.com/tinopetros/mifos-connector-py) installs from its release tag, on my machine and in the image
   - It's private, so whatever installs it needs read access: my SSH key here, and one fine-grained PAT, read-only on that repo, with no expiry
   - Actions, for `make check`: the PAT as the `MIFOS_CONNECTOR_TOKEN` repo secret
   - Cloud Build: the PAT as `mifos-connector-token` in `ourfos-prod`'s Secret Manager, for `package` only. It builds the connector's wheel, and the image installs that: no token in the Docker build or the image
   - Made by hand: infra's README, bootstrap 12
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
