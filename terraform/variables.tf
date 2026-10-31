# Both from env/<env>.tfvars
variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

# ourfos-api's region and domain. Cloud Run maps a domain in europe-west1 but not yet in africa-south1, and a load
# balancer costs more than ourfos can spend: until then, only ourfos-api runs there (#41)
variable "api_region" {
  type = string
}

variable "api_domain" {
  description = "Mapped to ourfos-api once verified in Search Console. None: only its run.app URL"
  type        = string
  default     = null
}

variable "services_image" {
  description = "Built by `make build`, tagged with a hash of services/"
  type        = string
}

variable "api_image" {
  description = "Built by `make build`, tagged with a hash of services/ and web/"
  type        = string
}

variable "build_version" {
  description = "The commit the image was built from, which the UI shows: Cloud Build's SHORT_SHA, or git's"
  type        = string
  default     = "unknown"
}

variable "ui_access" {
  description = "Who IAP lets into the UI, as IAM members: user:, group:, or domain:"
  type        = list(string)
}

variable "notify_to" {
  description = "Per form: who its emails go to, beside whoever submitted it"
  type        = map(list(string))

  validation {
    condition     = length(setsubtract(["requisition", "vehicle_log", "loan_approval", "write_off"], keys(var.notify_to))) == 0
    error_message = "Every form needs its list."
  }
}

variable "reply_to" {
  description = "Per form, only where replies shouldn't go to lekkai@ alone"
  type        = map(list(string))
  default     = {}
}

variable "simulate" {
  description = "Whether fixtures may force stubs and failures. Dev only"
  type        = bool
  default     = false
}

variable "mifos" {
  description = "Where we post, not who as: the user is a pair of secrets made by hand (docs/phase11/tdd.md, step 2)"
  type = object({
    base_url  = string
    tenant_id = string
    office_id = optional(number, 1)
    currency  = optional(string, "USD")
    # Off until the server has a certificate we can check (docs/phase11/adr.md 5)
    verify_ssl = optional(bool, true)
    # Whether our own forms' submissions post. A Google Form's link says so for its own, with &mifos=
    post = optional(bool, true)
  })

  # default is the books (docs/phase11/adr.md 4)
  validation {
    condition     = var.mifos.tenant_id != "default" || var.project_id == "ourfos-prod"
    error_message = "Only ourfos-prod posts to the default tenant."
  }
}

variable "mifos_syncs" {
  description = "Mifos's lists kept in the mifos bucket each night, and when, in New York's time. Prod only"
  type        = map(object({ schedule = string }))
  default     = {}
  validation {
    condition     = alltrue([for k in keys(var.mifos_syncs) : contains(["clients", "loans", "manual_journal_entries"], k)])
    error_message = "The mifos sync knows clients, loans and manual_journal_entries only."
  }
  validation {
    condition     = length(var.mifos_syncs) == 0 || var.project_id == "ourfos-prod"
    error_message = "Only ourfos-prod mirrors Mifos: dev's tenant is a copy of prod's, and overloaded already."
  }
}

variable "scheduler_region" {
  description = "Cloud Scheduler has no africa-south1. A job holds only its schedule and one call (docs/phase12/adr.md 10)"
  type        = string
  default     = "europe-west1"
}
