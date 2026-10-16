output "breaker_webhook" {
  description = "Used once, for the breaker drill in dev. Anyone holding it can trip the breaker."
  value       = azurerm_automation_webhook.breaker.uri
  sensitive   = true
}
