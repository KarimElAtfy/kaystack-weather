output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  value = data.azurerm_subscription.current.subscription_id
}

output "client_ids" {
  description = "plan goes to the repo variable AZURE_CLIENT_ID_PLAN, apply and deploy to AZURE_CLIENT_ID in the prod and release environments."
  value       = { for name, identity in azurerm_user_assigned_identity.ci : name => identity.client_id }
}

output "state_storage_account" {
  value = azurerm_storage_account.state.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}
