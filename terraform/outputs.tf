output "trigger_url" {
  value = google_cloudfunctions2_function.trigger.url
}

output "services_url" {
  value = google_cloud_run_v2_service.services.uri
}

output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

# What to add at the DNS provider for api_domain, once
output "api_dns" {
  value = [for m in google_cloud_run_domain_mapping.api : m.status[0].resource_records]
}
