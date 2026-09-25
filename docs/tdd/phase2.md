# Phase 2: CI/CD

## Goal

- Ship this repo the way [lekka-ourfos-infra](https://github.com/tinopetros/lekka-ourfos-infra) ships: checks on every PR, dev on merge, prod on a tag
- A human only merges and tags. Everything else runs unattended
- "Dev passed" means the workflow actually worked on dev, not just that Terraform applied

## Shape

```
PR ──────────▶ GitHub Actions: tf fmt · tf validate · uv lock --check · ruff        (no GCP credentials)

merge to main ▶ Cloud Build lekka-ourfos-dev   package · build · apply dev · smoke dev · plan prod
tag 0.1.0 ────▶ Cloud Build lekka-ourfos-prod  dev passed on this commit? · package · build · apply prod · smoke prod
```

- Both triggers live in `ourfos-prod`, next to infra's, and run as their own deployer: `ourfos-app-deployer@ourfos-prod`
- Read the prod plan in the dev build's log, then tag that commit to release it
- **Smoke** runs `happy` (must end `done`) and `classify-400` (must end `handed_over`) through the public trigger, and fails the build otherwise
- **Build per env:** each project has its own `ourfos` registry. The image tag is a hash of `services/`, so prod gets an image built from exactly the source dev ran

## CI calls the Makefile

- Every build step is a `make` target, so running it by hand does what CI does
- `ENV=dev|prod` picks the project, its tfvars (`terraform/env/<env>.tfvars`) and its own Terraform data dir, so dev and prod state can never get mixed up
- `make check` is exactly what the PR runs
- Terraform pinned to 1.16.4 everywhere, same as infra

## Bootstrapped, once

By hand on purpose: this is the identity Terraform runs as, so Terraform does not manage its own permissions.

_Filled in as it is done._

## Done when

- A PR shows the checks, and a broken format or stale lock fails them
- A build of this branch through the real dev trigger goes green: dev applied, smoke passed, prod planned
- The prod trigger refuses a commit that never passed dev

## Not in this phase

- Alerting (README TODO)
- Anything about the workflow itself
