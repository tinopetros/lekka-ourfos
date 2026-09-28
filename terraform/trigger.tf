resource "google_storage_bucket_object" "trigger" {
  name   = "trigger-${filemd5(var.trigger_zip)}.zip"
  bucket = local.sources_bucket
  source = var.trigger_zip
}

resource "google_cloudfunctions2_function" "trigger" {
  name     = "trigger"
  location = var.region

  build_config {
    runtime           = "python313"
    entry_point       = "trigger"
    docker_repository = data.google_artifact_registry_repository.ourfos.id
    service_account   = data.google_service_account.this["build"].name
    source {
      storage_source {
        bucket = local.sources_bucket
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
    # Made by hand, value and all (docs/phase6/tdd.md, Bootstrapped, once). Read when an instance starts
    secret_environment_variables {
      key        = "TRIGGER_TOKEN"
      project_id = var.project_id
      secret     = "trigger-token"
      version    = "latest"
    }
  }
}

# Anyone can reach it, since the form can't mint ID tokens. The function wants a bearer token
resource "google_cloud_run_v2_service_iam_member" "trigger_public" {
  name     = google_cloudfunctions2_function.trigger.service_config[0].service
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
