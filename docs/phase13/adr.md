# Phase 13: decisions and shortcuts

### 1. The UI is in this repo, in `web/`

- One PR for both sides of a change, and one source for types
- Infra stays in its own repo: what's set up once, with more rights than the deployer has

### 2. A BFF, `ourfos-api`, beside `ourfos-services`

- Same code, its own service and service account
- Not taken: **letting the UI call `ourfos-services`**. Its routes are a workflow's steps: they trust that a workflow called them, in order, and check no user. Opened to browsers, anyone signed in could call a step such as `post` directly
- For later, a leaning rather than a rule:
  - Writes outside us, to Mifos or by email, go through workflows: something has to retry, hand over, and never do it twice
  - Reads, and changes to our own data, the API does itself. Outside reads with read-only credentials where we can: Gmail's `gmail.readonly`, and a Mifos user that can only read. The existing Mifos user may do until release 1.0.0
  - A read that takes minutes, like Mifos's journal entries today, runs in the background, and the UI picks up the result

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
- `/api/me` says which environment and version, with who you are: one call before anything shows

### 9. Lists are latest activity first

- A submission that failed validation has no answers, so no `submitted_at`, and Firestore leaves a document out of a query ordered by a field it lacks. Every submission has `updated_at`
- Cursor paginated: the same cost on any page, unlike an offset, which Firestore bills for every document it skips
- The cost: a submission whose run moves on while you page can show twice, or not at all, until you refresh

### 10. No permissions yet

- Everyone at `lekkacredit.com` gets through IAP, and sees everything, journal entries included
- The cost: anyone in the company can read every submission and entry until phase 15 narrows it by group. Nobody can change anything

### 11. What comes after

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
