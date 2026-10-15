locals {
  owner_object_id = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "owner_state" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.owner_object_id
  principal_type       = "User"
}
