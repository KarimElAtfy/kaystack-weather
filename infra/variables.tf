variable "environment" {
  type        = string
  description = "prod or dev. Selects the state encryption key tfstate-<environment>."

  validation {
    condition     = contains(["prod", "dev"], var.environment)
    error_message = "The environment must be prod or dev."
  }
}
