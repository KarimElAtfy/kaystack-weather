variable "subscription_id" {
  type        = string
  description = "The personal pay-as-you-go subscription. Required so that a stale az login can never point the bootstrap at another subscription."
}

variable "alert_email" {
  type        = string
  description = "Inbox for budget and cost anomaly mails. Passed as TF_VAR_alert_email, never committed."
}
