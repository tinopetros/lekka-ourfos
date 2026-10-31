# expense for requisitions, intake for every form that's only received and acknowledged (docs/phase10/tdd.md),
# correction for a posted requisition (docs/phase12/tdd.md), action for what a person does from the UI, such as
# marking a handed-over requisition done, and mifos-sync for Mifos's clients, loans and manual
# journal entries into the mifos bucket.
# Each gets lib's plumbing under its own steps: all are maps of subworkflows (docs/phase10/adr.md 2)
resource "google_workflows_workflow" "this" {
  for_each                = toset(["expense", "intake", "correction", "action", "mifos-sync"])
  name                    = each.key
  region                  = var.region
  service_account         = local.sa.workflow
  source_contents         = join("\n", [for f in [each.key, "lib"] : file("${path.module}/../workflows/${f}.workflows.yaml")])
  execution_history_level = "EXECUTION_HISTORY_DETAILED"
  call_log_level          = "LOG_ERRORS_ONLY"
  deletion_protection     = false

  user_env_vars = {
    SERVICES_URL = google_cloud_run_v2_service.services.uri
    SIMULATE     = var.simulate ? "on" : "off"
  }
}

# Each night, one job a kind, as ourfos-api: it already starts workflows. In New York's time, which keeps both
# New York's evening and Harare's early morning quiet. Prod only: dev mirrors nothing from Mifos
resource "google_cloud_scheduler_job" "mifos_sync" {
  for_each  = var.mifos_syncs
  name      = "mifos-sync-${each.key}"
  region    = var.scheduler_region
  schedule  = each.value.schedule
  time_zone = "America/New_York"

  # Only starting the run is retried here. The run retries its own steps
  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.this["mifos-sync"].id}/executions"
    body        = base64encode(jsonencode({ argument = jsonencode({ kind = each.key }) }))
    headers     = { "Content-Type" = "application/json" }

    oauth_token {
      service_account_email = local.sa.api
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
