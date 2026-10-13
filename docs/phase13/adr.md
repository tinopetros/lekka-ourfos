# Phase 13: decisions and shortcuts

### 1. The UI is in this repo, in `web/`

- One PR for both sides of a change, and one source for types
- Infra stays in its own repo: what's set up once, with more rights than the deployer has

### 2. A BFF, `ourfos-api`, beside `ourfos-services`

- Same code, its own service and service account. Browsers never reach the routes that post to Mifos
- Its actions, later, start workflows. Only workflows touch Mifos
- Not taken: **opening `ourfos-services`** to the UI. One auth bug from the money

### 3. IAP for sign-in

- Google does the sign-in, the session and its cookie. We verify a signed header
- Locally, your ADC account is who you are
- Not taken: **our own OAuth and sessions**, as ourfos-v2. Code to own, for nothing we need
- The cost: tied to GCP. A native app, or anything outside a browser, needs a token path

### 4. TS types are generated from Pydantic

- One definition: Pydantic → OpenAPI → TypeScript. CI fails when they drift
- Not taken: **types kept twice by hand**, which drift; **Conjure**, heavy for one Python service

### 5. React Router, until we need more

- Familiar, and enough for lists and a sheet
- Routes in one file, search params through one hook: moving to TanStack Router stays cheap

### 6. Server data in TanStack Query, UI state in Zustand

- Caching, refetching and polling come with Query
- Not taken: **fetched data in Zustand stores**, as ourfos-v2

### 7. The API serves the UI

- Same origin: no CORS, and IAP's cookie just works
- Not taken: **Firebase Hosting**, until a CDN matters

### 8. One build, the environment at runtime

- Dev and prod run the same image, as the release gate assumes

### 9. No permissions yet

- Whoever IAP lets through sees everything, journal entries included
- The cost: fine while the access list is short and trusted. Phase 15 adds them

### 10. What comes after

- **Phase 14, submitting forms from the UI**
  - The API saves the submission and starts the workflow the trigger would. One path for a Google Form and the UI
  - `submitted_by` is who's signed in; `source`, `ui` or `google-form`
  - A typed definition per form: react-hook-form and zod. Attachments to GCS through signed URLs
  - Every route declares its permission, e.g. `forms:requisition:submit`, all granted to everyone for now. Phase 15 then changes the policy, not the routes
- **Phase 15, journal entry actions, and permissions**
  - Workspace groups, nested ones too, synced onto `users`; roles from a policy file in the repo, and roles granted to a person
  - `can` and `scope` on the server, so lists only hold what you may see. `/me` lists your permissions, for the UI to show
  - `journal_entries:read`, `:correct`, `:reverse`, through the `correction` workflow. `requested_by` is who's signed in, never the request body. The UI follows the run until it ends
  - An entry stuck `reversing` gets its screen: record the mirror's id, or clear it (phase 12 ADR 4)
- **Later**
  - A reversal with no requisition, its own workflow (phase 12 ADR 3)
  - A PWA or a native app: camera, offline, Wi-Fi only (#30)
