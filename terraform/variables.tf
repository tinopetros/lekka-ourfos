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
  description = "Who every requisition's emails go to, beside whoever submitted it"
  type        = list(string)
}

variable "simulate" {
  description = "Whether fixtures may force stubs and failures. Dev only"
  type        = bool
  default     = false
}
