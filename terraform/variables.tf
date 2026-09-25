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
