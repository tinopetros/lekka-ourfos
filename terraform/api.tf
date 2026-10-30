# ourfos-api: what the UI reads, and the UI itself, behind IAP. Its own image, and its own account, which reads the
# database, starts workflows, and asks ourfos-services for what only they read, Mifos's accounts.
# In its own region, for its own domain: the rest of ourfos stays in var.region
data "google_project" "this" {}

locals {
  # IAP's own account, made by the bootstrap. It calls the service once it has signed someone in
  iap_agent = "service-${data.google_project.this.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_service" "api" {
  name                = "ourfos-api"
  location            = var.api_region
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
          # Where the workflows it starts run: the rest of ourfos's region, not its own
          REGION = var.region
          # A submission's workflow posts to Mifos only where this environment does
          POST_TO_MIFOS = tostring(var.mifos.post)
          # What it reads but holds no credentials for, Mifos's accounts, it asks of these, as itself. Their URL by
          # its pattern: the services already name this one's, and the two can't each wait on the other
          SERVICES_URL = "https://ourfos-services-${data.google_project.this.number}.${var.region}.run.app"
          # What IAP's signed header must be for: this service, and no other
          IAP_AUDIENCE = "/projects/${data.google_project.this.number}/locations/${var.api_region}/services/ourfos-api"
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
  location = var.api_region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.iap_agent}"
}

# Who IAP lets through: everyone listed sees everything for now
resource "google_iap_web_cloud_run_service_iam_member" "ui_access" {
  for_each = toset(var.ui_access)

  location               = var.api_region
  cloud_run_service_name = google_cloud_run_v2_service.api.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}

# The UI at its own address, with a certificate Google keeps. Needs the domain verified in Search Console with
# ourfos-app-deployer@ourfos-prod as an owner, and a CNAME to ghs.googlehosted.com at the DNS provider (api_dns)
resource "google_cloud_run_domain_mapping" "api" {
  count = var.api_domain == null ? 0 : 1

  location = var.api_region
  name     = var.api_domain
  metadata {
    namespace = var.project_id
  }
  spec {
    route_name = google_cloud_run_v2_service.api.name
  }
}
