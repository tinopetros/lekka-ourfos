# expense for requisitions, intake for every form that's only received and acknowledged (docs/phase10/tdd.md).
# Each gets lib's plumbing under its own steps: both are maps of subworkflows (docs/phase10/adr.md 2)
resource "google_workflows_workflow" "this" {
  for_each                = toset(["expense", "intake"])
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
