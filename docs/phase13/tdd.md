# Phase 13: establish-fe

## Goal

- A UI, on dev and prod, signed in with Google, that lists each form's submissions and our journal entries, and opens any of them
- Reads only: no actions, and no permissions beyond who may sign in (ADR 10)
- A foundation the next phases build on: actions, then permissions (ADR 11)

## Steps

1. **`ourfos-api`**, a Cloud Run service in each project, from the same Python package as `ourfos-services` (ADR 2)
   - Reads Firestore, and writes only `users`. No Mifos, no workflows
   - `GET /api/me`: who you are, and the environment and version (ADR 8)
   - `GET /api/forms`, `GET /api/forms/{form}/submissions`, `GET /api/forms/{form}/submissions/{id}`
   - `GET /api/journal_entries`, `GET /api/journal_entries/{transaction_id}`
   - Lists newest first, by `received_at`, cursor paginated (ADR 9)
   - Every request logged with its `user`, method, path, status and latency
   - Serves the built UI, same origin (ADR 7)
2. **Response models** in Pydantic, one per route: `Me`, `FormInfo`, `SubmissionSummary`, `Submission` (answers, runs, emails, journal entries), `JournalEntry`, and a page of each list
   - A run has its workflow's shape: `ExpenseRun`, `CorrectionRun`, `IntakeRun`, each adding its own fields to what every run has, and `UnknownRun` for a workflow the API doesn't know yet. TypeScript narrows on `workflow`
   - `views.py` turns stored documents into them, every shape they've had: what a document lacks comes back empty, and a run whose own fields don't read still shows how it ended
   - The requisition's file questions are titled on its `Files` model, which the emails and the UI both read
3. **`received_at`** on every submission, with its first status, valid or not, and never moved (ADR 9). Earlier ones backfilled: dev's on Oct 14
4. **Sign-in** (ADR 3)
   - IAP in front of `ourfos-api`. Everyone at `lekkacredit.com` gets through
   - `current_user`, a dependency every route takes, verifies IAP's signed header
   - Locally, the identity is your ADC account. Refused on Cloud Run
   - `users/{email}`: `email`, `first_seen`, `last_seen`, written on sign-in, in the background, at most every 5 minutes. A name comes with Workspace's directory, with permissions
5. **Types**: FastAPI's OpenAPI → `openapi-typescript` → `web/src/lib/api/schema.d.ts`, called through `openapi-fetch`. `make types` makes them; CI fails when they're stale (ADR 4)
6. **`web/`**
   - Vite, React 19, TypeScript strict, Tailwind 4, shadcn (from ourfos-v2)
   - React Router 8 (ADR 5); TanStack Query for server data, Zustand for UI state only (ADR 6)
   - A shell: a sidebar of the forms, from the API, and Journal
   - A table per list, its page in the URL; a row opens a read-only sheet, a route of its own, so an open sheet is a link. Filters wait for the indexes they need
   - Responsive
   - Banners: red **TEST** on dev, **LOCAL → dev data** locally. Test submissions have a badge, prod's too
7. **Images** (ADR 8): `ourfos-api`'s own, `services/api.Dockerfile`, its UI built in a Node stage; the services' as before. Each tagged by a hash of what goes in it. The environment is read at runtime, so the commit that passed on dev is the one released. The UI shows the commit
8. **Terraform**: `ourfos-api` on its own image, `iap_enabled`, IAP's agent as its invoker, and `ui_access` in each env's tfvars: who IAP lets through

## Local

- `make web`: installs when the lock changed, makes the types, then runs Vite on :5173 and the API on :8000, on your ADC, reading dev's Firestore. `ACT_AS=<email>` to be someone else. Never prod's
- `make types` after changing `services/api/models.py`; Vite and the API reload on their own
- The API's docs, on what it answers: http://localhost:8000/docs

## Smoke

- IAP turns away a request that isn't signed in
- Through IAP, signed in, waits on how a build can sign in to IAP on Cloud Run: checked by hand on dev for now

## Bootstrapped, once

**1. Infra** (tinopetros/lekka-ourfos-infra#20), in both projects: `ourfos-api@`, our deployer's right to act as it, and IAP's service agent, which calls the service. Applied before this merges: Terraform here looks the account up, and `plan-prod` fails until prod has it too

**2. The deployer manages who IAP lets in.** Its own project role, so by hand, like its others (docs/phase2). Run on Oct 14:

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com
for P in ourfos-dev ourfos-prod; do
  gcloud projects add-iam-policy-binding "$P" --condition=None \
    --member="serviceAccount:$SA" --role=roles/iap.admin
done
```

**3. Who gets in**: `ui_access` in `terraform/env/<env>.tfvars`. Everyone at `lekkacredit.com` for now; groups, and what each may see, come with permissions (ADR 10)
