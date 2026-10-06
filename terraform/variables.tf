# Both from env/<env>.tfvars
variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "services_image" {
  description = "Built by `make build`, tagged with a hash of services/"
  type        = string
}

variable "trigger_zip" {
  description = "Packaged by `make package`"
  type        = string
  default     = "../.build/trigger.zip"
}

variable "notify_to" {
  description = "Per form: who its emails go to, beside whoever submitted it"
  type        = map(list(string))

  validation {
    condition     = length(setsubtract(["requisition", "vehicle_log", "loan_approval", "write_off"], keys(var.notify_to))) == 0
    error_message = "Every form needs its list."
  }
}

variable "test_to" {
  description = "Who of the submitters a test run also emails, beside lekkai@ (docs/release1/adr.md 3)"
  type        = list(string)
  default     = []
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
  })

  # default is the books (docs/phase11/adr.md 4)
  validation {
    condition     = var.mifos.tenant_id != "default" || var.project_id == "ourfos-prod"
    error_message = "Only ourfos-prod posts to the default tenant."
  }
}

variable "syncs" {
  description = "What's synced from Mifos each night, and when, in Harare's time (docs/phase12/tdd.md, step 7)"
  type        = map(object({ schedule = string }))
  default = {
    journal_entries = { schedule = "0 23 * * *" }
  }
}
