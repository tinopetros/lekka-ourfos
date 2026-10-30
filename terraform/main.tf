terraform {
  # 1.16.4 in CI and Cloud Build too. A newer one would rewrite state they cannot read
  required_version = "~> 1.16.4"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.2"
    }
  }

  # bucket comes from `make tf-init`, one per project: <project>-tfstate
  backend "gcs" {
    prefix = "ourfos"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Infra owns registries. Fails here until it exists
data "google_artifact_registry_repository" "ourfos" {
  location      = var.region
  repository_id = "ourfos"
}

# Infra makes what we run as and build with (modules/ourfos-app). Fails here
# until it exists, like the registry
data "google_service_account" "this" {
  for_each   = toset(["workflow", "services", "build", "api"])
  account_id = "ourfos-${each.key}"
}

locals {
  sa = { for k, v in data.google_service_account.this : k => v.email }
}
