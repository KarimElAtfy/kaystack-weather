locals {
  owner_object_id = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "owner_vault" {
  for_each = toset(["Key Vault Crypto Officer", "Key Vault Secrets Officer"])

  scope                = azurerm_key_vault.main.id
  role_definition_name = each.key
  principal_id         = local.owner_object_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "owner_state" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.owner_object_id
  principal_type       = "User"
}
