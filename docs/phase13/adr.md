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

### 8. An image per service, built once per commit, the environment at runtime

- `ourfos-services` and `ourfos-api` each have their own Dockerfile and start command: nothing overrides what an image runs
- One package list for both: the API's image carries what it never imports, ADK and the Mifos connector among them. The cost: a heavier image, and maybe a slower cold start. Leaner only if a measured cold start asks for it: a second package list, or the shared code as a package of its own
- Each is tagged by a hash of what goes in it, so a UI change rebuilds only the API's
- Dev and prod each build their own images, from the same commit and the same way: the release gate checks the commit
- Not taken: **one image, the API's start command overridden in Terraform**. Hard to tell which service runs what, and every UI change rebuilt the services
- `/api/me` says which environment and version, with who you are: one call before anything shows

### 9. Lists are newest first, by when we received them

- `received_at` is set on a submission with its first status, valid or not, and never moved. Not `submitted_at`: an invalid submission's never validated, and Firestore leaves a document out of a query ordered by a field it lacks
- Submissions from before it were backfilled from their earliest run's start, by a one-off script: dev on Oct 14, prod at release
- Cursor paginated: the same cost on any page, unlike an offset, which Firestore bills for every document it skips
- Latest activity, once there's an activity list to sort by

### 10. No permissions yet

- Everyone at `lekkacredit.com` gets through IAP, and sees everything, journal entries included
- The cost: anyone in the company can read every submission and entry until phase 15 narrows it by group. Nobody can change anything

### 11. What comes after

- **Phase 14, submitting forms from the UI**
  - The API saves the submission and starts the workflow the trigger would. One path for a Google Form and the UI
  - `submitted_by` is who's signed in; `source`, `ui` or `google-form`
  - A typed definition per form: react-hook-form and zod. Attachments to GCS through signed URLs
  - Toasts, for an action that fails: `MutationCache`'s `onError`, and shadcn's Sonner. A page that can't load already says so where it is
  - Every route declares its permission, e.g. `forms:requisition:submit`, all granted to everyone for now. Phase 15 then changes the policy, not the routes
- **Phase 15, journal entry actions, and permissions**
  - Workspace groups, nested ones too, synced onto `users`; roles from a policy file in the repo, and roles granted to a person
  - `can` and `scope` on the server, so lists only hold what you may see. `/me` lists your permissions, for the UI to show
  - `journal_entries:read`, `:correct`, `:reverse`, through the `correction` workflow. `requested_by` is who's signed in, never the request body. The UI follows the run until it ends
  - An entry stuck `reversing` gets its screen: record the mirror's id, or clear it (phase 12 ADR 4)
- **Later**
  - A reversal with no requisition, its own workflow (phase 12 ADR 3)
  - A PWA or a native app: camera, offline, Wi-Fi only (#30)
  - Integration tests from the UI's side: its client against the deployed API, with fixtures, as the backend's are (#34)

### 12. The UI's conventions, after bulletproof-react

A standard to start from, borrowed from [bulletproof-react](https://github.com/alan2207/bulletproof-react), and changed when we learn better

- **A folder per feature**: its pages, sheets and `api.ts`, its queries and their hooks, together. What features share goes in `components/` and `lib/`; what every page needs, `me` and the forms, in `lib/api`
- **Imports from `@/`**, never `../../`: moving a file breaks no one else's imports
- **The API's data in TanStack Query, what only the browser knows in Zustand** (ADR 6)
- **API errors in one place**: `unwrap` makes a failed call an `ApiError`, and `QueryState` shows it where the page is. Toasts come with actions
- **Tests beside what they test**, on Vitest and Testing Library
- **Types generated from the API**, never written by hand (ADR 4)
- **shadcn's components copied in**, ours to change (its CSS too: #33)

### 13. A record is a page of its own

- Part 1's sheets over the list gave way: a record has tabs, a history and files, and wants the room
- The way back is a breadcrumb to the page of the list you came from, carried in the browser's history, not the URL. A record opened from a shared link goes back to the list's first page
- Previous and next walk the list you came from, fetching its next or previous page when one runs out. Opened from a link, they walk the list's first page if it's there
- Not taken: **keeping the sheet**, which overlaid the list it needed the room of

### 14. Files open where you are, each from where it lives

- Drive's: its own preview, in a frame. It shows only what your Google account can open, which is Drive's permissions doing their job, and needs nothing of ours
- Ours, in GCS: the API streams them, behind IAP like everything else. Its account reads the attachments bucket, nothing more
- Not taken: **signed URLs** for ours, links that open for anyone holding them, and need the API to sign; **the API fetching Drive's as lekkai@**, which would show everyone every file, a choice for permissions (ADR 11)

### 15. The sidebar gets out of the way

- shadcn's, collapsible to icons. Collapsed on a record's page, unless you open it there, which keeps it open on records from then on
- Remembered in the browser, per browser: a preference, not a record. Gone in a private window, which falls back to the defaults

### 16. Search, when it comes, is one kind of record at a time

- Ids and response numbers are lookups; subjects match from their start, through a lowercased field and a range query
- A word in the middle of a subject, or of an answer, needs a search index: Firestore's own, if its Enterprise edition's text search fits, or a service beside it. Its own phase
- Part 2 has the search bar, as a look only
