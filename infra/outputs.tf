output "site_host_name" {
  description = "The default host name of the site, the target of the weather CNAME at the registrar."
  value       = azurerm_static_web_app.site.default_host_name
}

output "breaker_webhook" {
  description = "Used once, for the breaker drill in dev. Anyone holding it can trip the breaker."
  value       = azurerm_automation_webhook.breaker.uri
  sensitive   = true
}
