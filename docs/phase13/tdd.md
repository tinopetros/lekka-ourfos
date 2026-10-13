# Phase 13: establish-fe

## Goal

- A UI, on dev and prod, signed in with Google, that lists each form's submissions and our journal entries, and opens any of them
- Reads only: no actions, and no permissions beyond who may sign in (ADR 9)
- A foundation the next phases build on: actions, then permissions (ADR 10)

## Steps

1. **`ourfos-api`**, a Cloud Run service in each project, from the same Python package as `ourfos-services` (ADR 2)
   - Reads Firestore, and writes only `users`. No Mifos, no workflows
   - `GET /api/me`, `GET /api/config` (the environment)
   - `GET /api/forms`, `GET /api/forms/{form}/submissions`, `GET /api/forms/{form}/submissions/{id}`
   - `GET /api/journal_entries`, `GET /api/journal_entries/{transaction_id}`
   - Lists newest first, cursor paginated
   - Serves the built UI, same origin (ADR 7)
2. **Response models** in Pydantic, one per route: `Me`, `Config`, `SubmissionSummary`, `Submission` (answers, runs, emails, journal entries), `JournalEntry`, `Page[T]`. Firestore's documents are read through them
3. **Sign-in** (ADR 3)
   - IAP in front of `ourfos-api`. One Workspace group, or a short list, gets through
   - `current_user`, a dependency every route takes, verifies IAP's signed header
   - Locally, the identity is your ADC account. Refused on Cloud Run
   - `users/{email}`: `name`, `first_seen`, `last_seen`, written on sign-in
4. **Types**: FastAPI's OpenAPI → `openapi-typescript` → `web/src/lib/api`. CI fails when it's stale (ADR 4)
5. **`web/`**
   - Vite, React 19, TypeScript strict, Tailwind 4, shadcn (from ourfos-v2)
   - React Router 7 (ADR 5); TanStack Query for server data, Zustand for UI state only (ADR 6)
   - A shell: a sidebar of the forms, and Journal
   - A table per list, filters in the URL; a row opens a read-only detail sheet
   - Responsive
   - Banners: red **TEST** on dev, **LOCAL → dev data** locally. Test submissions have a badge, prod's too
6. **Build once** (ADR 8): one image, the API and the UI. The environment is read at runtime, so the commit that passed on dev is the one released
7. **Terraform**: the service, IAP and its access list, the service account's grants

## Local

- `make web`: Vite, against the API run locally on your ADC, reading dev's Firestore

## Smoke

- Dev's `ourfos-api` answers `/api/me` and both lists for the deployer, through IAP. How smoke authenticates through IAP is still to confirm
- `happy`'s submission and its journal entry are in the lists, and open

## Bootstrapped, once

- Infra: `iap.googleapis.com` enabled; the `ourfos-api` service account
- Workspace: the access group (Tino)
