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
3. **Connect.** Each instance of the service, when it starts, reads one journal entry from Mifos and logs `mifos connected`, or why not: it reaches Mifos, and logs in
4. **Post.** The classified lines as one journal entry:
   - the requisition's reference number as Mifos's reference, its response number until the form asks for one
   - labelled in its comments, reference number first: `Reference number: …. {subject}. Response number: …. Workflow run: …`
   - dated the day it was disbursed, or today
   - never twice: a run that has posted returns its transaction
   - never on a test run
5. **Read back.** What Mifos has, compared with what we posted, line by line (ADR 2). The run keeps it as `posted`: the transaction id, the date it's booked on, the office, the currency, and its lines
6. **The last email.** A reply in the thread: **Lekkai's action: POSTED**, the Mifos transaction ID, Mifos's lines, and that Lekkai may make mistakes (ADR 3). A test run's says **NOT POSTED**
7. **Prod.** Its tfvars and secrets, planned, not released

## Settings

- Defaults from the connector's own `.env`: the server's URL, office `1`
- Tenant: `demo` on dev, `default` on prod
- Currency: `USD`

## Smoke

- One fixture, `happy`, posts to `demo` for real on every dev build
- Every other fixture that reaches `post` keeps the stub

## Before prod's release

Reminders, for when we tag:

- Prod's requisition form asks for **Reference Number**, sent as `reference_number`, as dev's will. Until it does, prod's posts are referenced by response number
- Mifos's certificate: once the server has one, `verify_ssl` on in both tfvars (ADR 5)
