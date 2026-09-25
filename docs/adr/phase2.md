# Phase 2: decisions and shortcuts

### 1. Our own deployer, not infra's

- `ourfos-app-deployer@ourfos-prod`, made by hand like infra's `deployer`
- This repo needs far more than infra does: Cloud Run, Functions, Workflows, service accounts and acting as them. Sharing one identity would hand both repos the union

### 2. The deployer can grant exactly two project roles

- Our Terraform grants `logging.logWriter` (workflow) and `workflows.invoker` (trigger) project-wide, which needs `projectIamAdmin`, and that on its own is as good as owner
- So it is granted with a condition that only lets it add or remove those two roles
- **Revisit when** a new project-level grant shows up: add it to the condition, deliberately

### 3. Triggers are made by hand

- Same as infra. A trigger that Terraform manages is a trigger that can rewrite itself
- The README's "lekka-ourfos owns Cloud Build triggers" means: they run this repo, not that this repo's Terraform makes them

### 4. The prod gate checks the trigger too

- Infra's gate matches `_ENV` and the commit. Two repos now build in `ourfos-prod`, so ours also matches `TRIGGER_NAME=lekka-ourfos-dev`

### 5. A public trigger in prod

- ADR 5 of phase 1 still stands: anyone with the URL can start a run, now in prod too
- Accepted for now: only stubs are behind it, and nothing reaches prod without a human pushing a tag
- **Revisit** before anything real is behind it
