variable "project_id" {
  type    = string
  default = "ourfos-dev"
}

variable "region" {
  type    = string
  default = "africa-south1"
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
