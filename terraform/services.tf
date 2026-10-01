# Each form's name, as its add-on's sender name was, and who hears: the list in env/<env>.tfvars, and a Reply-To
# only where replies go elsewhere (docs/phase10/tdd.md)
locals {
  form_names = {
    requisition   = "Requisition Approval Request Form"
    vehicle_log   = "Vehicle Log Form"
    loan_approval = "Loan Approval Request Form"
    write_off     = "Write-off Request Form"
  }
  forms = {
    for form, name in local.form_names : form => merge(
      { name = name, notify_to = var.notify_to[form] },
      contains(keys(var.reply_to), form) ? { reply_to = var.reply_to[form] } : {},
    )
  }
}

resource "google_cloud_run_v2_service" "services" {
  name                = "ourfos-services"
  location            = var.region
  deletion_protection = false

  template {
    service_account = local.sa.services
    # docs/release1/adr.md 1
    scaling {
      max_instance_count = 1
    }
    max_instance_request_concurrency = 10
    containers {
      image = var.services_image
      # Up to 40 MB of attachments, and a base64 copy of them, beside ADK and the SDKs
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }

      dynamic "env" {
        for_each = {
          GOOGLE_GENAI_USE_VERTEXAI = "true"
          GOOGLE_CLOUD_PROJECT      = var.project_id
          GOOGLE_CLOUD_LOCATION     = "global"
          EXPENSER_MODEL            = "gemini-3.5-flash-lite"
          MODEL_ARMOR_TEMPLATE      = google_model_armor_template.expenser.id
          FIRESTORE_DATABASE        = "ourfos"
          WORKSPACE_SUBJECT         = "lekkai@lekkacredit.com"
          ATTACHMENTS_BUCKET        = "${var.project_id}-attachments"
          FORMS                     = jsonencode(local.forms)
          TEST_TO                   = join(",", var.test_to)
        }
        content {
          name  = env.key
          value = env.value
        }
      }
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
