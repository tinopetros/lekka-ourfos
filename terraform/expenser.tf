# Screens every prompt to expenser before the model sees it (ADR 6). Model
# Armor has no africa-south1 or global endpoint, so eu (ADR 7)
resource "google_model_armor_template" "expenser" {
  location    = "eu"
  template_id = "expenser"

  filter_config {
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }
  }
}

# The model and the screening, both called from ourfos-services
resource "google_project_iam_member" "services" {
  for_each = toset(["roles/aiplatform.user", "roles/modelarmor.user"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${local.sa.services}"
}
