variable "environment" {
  type        = string
  description = "prod or dev. Selects the state encryption key tfstate-<environment>."

  validation {
    condition     = contains(["prod", "dev"], var.environment)
    error_message = "The environment must be prod or dev."
  }
}

variable "timers_enabled" {
  type        = bool
  description = "Passed to the Function as TIMERS_ENABLED."
}

variable "arpa_secret_set" {
  type        = bool
  description = "True once arpa-app-token exists in kv-kaystack-meteo. Grants the Function read access to that one secret and passes it as ARPA_APP_TOKEN."
}

variable "breaker_alerts" {
  type        = bool
  description = "The six metric alerts that trip the breaker. Dev has the runbook but not the alerts, which would use up the free metric series."
}

variable "log_daily_cap_gb" {
  type        = number
  description = "Daily ingestion cap, set on both Log Analytics and Application Insights."
}

variable "immutable_days" {
  type        = number
  description = "Time-based retention on the forecasts and legacy containers, 0 for none. A lake holding protected blobs cannot be deleted, so dev has none."
}
