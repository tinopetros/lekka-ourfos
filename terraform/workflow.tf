resource "google_workflows_workflow" "requisition" {
  name                    = "requisition"
  region                  = var.region
  service_account         = local.sa.workflow
  source_contents         = file("${path.module}/../workflows/requisition.workflows.yaml")
  execution_history_level = "EXECUTION_HISTORY_DETAILED"
  call_log_level          = "LOG_ERRORS_ONLY"
  deletion_protection     = false

  user_env_vars = {
    SERVICES_URL = google_cloud_run_v2_service.services.uri
  }
}

resource "google_project_iam_member" "workflow_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${local.sa.workflow}"
}
