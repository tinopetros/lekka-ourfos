resource "google_storage_bucket" "sources" {
  name                        = "${var.project_id}-ourfos-sources"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_storage_bucket_object" "trigger" {
  name   = "trigger-${filemd5(var.trigger_zip)}.zip"
  bucket = google_storage_bucket.sources.name
  source = var.trigger_zip
}

resource "google_cloudfunctions2_function" "trigger" {
  name     = "trigger"
  location = var.region

  build_config {
    runtime           = "python313"
    entry_point       = "trigger"
    docker_repository = data.google_artifact_registry_repository.ourfos.id
    source {
      storage_source {
        bucket = google_storage_bucket.sources.name
        object = google_storage_bucket_object.trigger.name
      }
    }
  }

  service_config {
    service_account_email = local.sa.trigger
    environment_variables = {
      PROJECT_ID = var.project_id
      REGION     = var.region
      WORKFLOW   = google_workflows_workflow.requisition.name
    }
  }
}

# Public, for now (ADR 5)
resource "google_cloud_run_v2_service_iam_member" "trigger_public" {
  name     = google_cloudfunctions2_function.trigger.service_config[0].service
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_project_iam_member" "trigger_starts_workflows" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${local.sa.trigger}"
}
