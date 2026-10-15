# ourfos-api: what the UI reads, and the UI itself, behind IAP. Its own image, and its own account, which can read
# the database and post nothing
data "google_project" "this" {}

locals {
  # IAP's own account, made by the bootstrap. It calls the service once it has signed someone in
  iap_agent = "service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_service" "api" {
  name                = "ourfos-api"
  location            = var.region
  deletion_protection = false
  # Anyone can reach it, and IAP turns away whoever it can't sign in, or who isn't in ui_access
  ingress     = "INGRESS_TRAFFIC_ALL"
  iap_enabled = true

  template {
    service_account = local.sa.api
    scaling {
      max_instance_count = 2
    }
    containers {
      image = var.api_image
      resources {
        limits = { cpu = "1", memory = "512Mi" }
        # A cold start is someone waiting on a page
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = {
          GOOGLE_CLOUD_PROJECT = var.project_id
          FIRESTORE_DATABASE   = "ourfos"
          ATTACHMENTS_BUCKET   = "${var.project_id}-attachments"
          ENVIRONMENT          = trimprefix(var.project_id, "ourfos-")
          VERSION              = var.build_version
          # What IAP's signed header must be for: this service, and no other
          IAP_AUDIENCE = "/projects/${data.google_project.this.number}/locations/${var.region}/services/ourfos-api"
        }
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "iap_invokes_api" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.iap_agent}"
}

# Who IAP lets through: everyone listed sees everything for now
resource "google_iap_web_cloud_run_service_iam_member" "ui_access" {
  for_each = toset(var.ui_access)

  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.api.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}
