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

In order, from a shell logged in as a project owner.

**1. The deployer.** After infra has made our accounts and bucket (`modules/ourfos-app`).

```bash
gcloud iam service-accounts create ourfos-app-deployer --project=ourfos-prod \
  --display-name="Cloud Build deployer for lekka-ourfos"
```

**2. What it may do, in both projects.** Deploy our three kinds of resource, and act as only the accounts infra made for us (ADR 6):

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  for R in run.admin cloudfunctions.admin workflows.admin cloudbuild.builds.editor serviceusage.serviceUsageConsumer; do
    gcloud projects add-iam-policy-binding "$P" --condition=None \
      --member="serviceAccount:$SA" --role="roles/$R"
  done
  # Project IAM, but only ever these two roles (ADR 2). ^;^ because the expression has commas
  gcloud projects add-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin \
    --condition='^;^expression=api.getAttribute("iam.googleapis.com/modifiedGrantsByRole", []).hasOnly(["roles/logging.logWriter", "roles/workflows.invoker"]);title=only-two-roles'
  # Act as ours, and nobody else
  for A in trigger workflow services build; do
    gcloud iam service-accounts add-iam-policy-binding "ourfos-$A@$P.iam.gserviceaccount.com" --project="$P" \
      --member="serviceAccount:$SA" --role=roles/iam.serviceAccountUser
  done
  # Our bucket and state, the registry infra owns
  for B in "$P-ourfos-sources" "$P-tfstate"; do
    gcloud storage buckets add-iam-policy-binding "gs://$B" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin
  done
  # gcloud builds submit looks the staging bucket up before uploading to it
  gcloud storage buckets add-iam-policy-binding "gs://$P-ourfos-sources" \
    --member="serviceAccount:$SA" --role=roles/storage.legacyBucketReader
  gcloud artifacts repositories add-iam-policy-binding ourfos --project="$P" --location=africa-south1 \
    --member="serviceAccount:$SA" --role=roles/artifactregistry.reader
done

# The build itself: its logs, and reading history for "dev passed?"
for R in logging.logWriter cloudbuild.builds.viewer; do
  gcloud projects add-iam-policy-binding ourfos-prod --condition=None \
    --member="serviceAccount:$SA" --role="roles/$R"
done
```

**3. Link the repo** to the connection infra already made (the GitHub app must be allowed to see it):

```bash
gcloud builds repositories create lekka-ourfos --project=ourfos-prod --region=africa-south1 \
  --connection=tinopetros-github --remote-uri=https://github.com/tinopetros/lekka-ourfos.git
```

**4. The two triggers**, both running `cloudbuild.yaml` as the deployer:

```bash
REPO=projects/ourfos-prod/locations/africa-south1/connections/tinopetros-github/repositories/lekka-ourfos
SA=projects/ourfos-prod/serviceAccounts/ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

gcloud builds triggers create github --project=ourfos-prod --region=africa-south1 \
  --name=lekka-ourfos-dev --repository=$REPO --branch-pattern='^main$' \
  --build-config=cloudbuild.yaml --service-account=$SA --substitutions=_ENV=dev

gcloud builds triggers create github --project=ourfos-prod --region=africa-south1 \
  --name=lekka-ourfos-prod --repository=$REPO --tag-pattern='^[0-9]+\.[0-9]+\.[0-9]+$' \
  --build-config=cloudbuild.yaml --service-account=$SA --substitutions=_ENV=prod
```

**5. Try it before merging**, on this branch through the real dev trigger:

```bash
gcloud builds triggers run lekka-ourfos-dev --project=ourfos-prod --region=africa-south1 --branch=cicd
```

## Done when

- A PR shows the checks, and a broken format or stale lock fails them
- A build of this branch through the real dev trigger goes green: dev applied, smoke passed, prod planned
- The prod trigger refuses a commit that never passed dev

## Not in this phase

- Alerting (README TODO)
- Anything about the workflow itself
