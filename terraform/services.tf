resource "google_cloud_run_v2_service" "services" {
  name                = "ourfos-services"
  location            = var.region
  deletion_protection = false

  template {
    service_account = local.sa.services
    containers {
      image = var.services_image
    }
  }
}

# Private: only the workflow can call it
resource "google_cloud_run_v2_service_iam_member" "workflow_invokes_services" {
  name     = google_cloud_run_v2_service.services.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.sa.workflow}"
}
