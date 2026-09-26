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
