# In prod these are created by the apply identity, whose delegation condition
# allows only these roles and only principal_type ServicePrincipal.

resource "azurerm_role_assignment" "function_host_storage" {
  scope                = module.func.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_function_app_flex_consumption.main.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "function_data" {
  for_each = {
    lake   = module.lake.id
    public = module.public.id
  }

  scope                = each.value
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.main.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

# Application Insights has local authentication off, so telemetry is sent with
# the Function's identity.
resource "azurerm_role_assignment" "function_telemetry" {
  scope                = azurerm_application_insights.main.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_function_app_flex_consumption.main.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

# A role assignment cannot target a secret that does not exist yet, hence the
# switch: it goes on once the owner has stored the token by hand.
resource "azurerm_role_assignment" "function_arpa_token" {
  count = var.arpa_secret_set ? 1 : 0

  scope                = "${data.azurerm_key_vault.shared.id}/secrets/arpa-app-token"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_function_app_flex_consumption.main.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "breaker_public" {
  scope                = module.public.id
  role_definition_name = "Storage Account Contributor"
  principal_id         = azurerm_automation_account.breaker.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "breaker_function" {
  scope                = azurerm_function_app_flex_consumption.main.id
  role_definition_name = "Website Contributor"
  principal_id         = azurerm_automation_account.breaker.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}
