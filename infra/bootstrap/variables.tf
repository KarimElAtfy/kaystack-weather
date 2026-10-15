variable "subscription_id" {
  type        = string
  description = "The personal pay-as-you-go subscription. Required so that a stale az login can never point the bootstrap at another subscription."
}
