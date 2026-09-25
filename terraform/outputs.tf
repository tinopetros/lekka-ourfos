output "trigger_url" {
  value = google_cloudfunctions2_function.trigger.url
}

output "services_url" {
  value = google_cloud_run_v2_service.services.uri
}
