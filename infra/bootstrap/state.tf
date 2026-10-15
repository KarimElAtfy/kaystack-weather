resource "azurerm_storage_account" "state" {
  name                     = local.state_account_name
  resource_group_name      = azurerm_resource_group.shared.name
  location                 = local.location
  account_tier             = "Standard"
  account_replication_type = "ZRS"
  min_tls_version          = "TLS1_2"

  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  local_user_enabled              = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  tags = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "state" {
  for_each = toset(["bootstrap", "prod", "dev"])

  name               = each.key
  storage_account_id = azurerm_storage_account.state.id

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_management_lock" "state" {
  name       = "keep-state"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Every OpenTofu state of the project lives here."
}

resource "azurerm_key_vault" "main" {
  name                       = local.key_vault_name
  location                   = local.location
  resource_group_name        = azurerm_resource_group.shared.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 90

  tags = local.tags

  lifecycle {
    prevent_destroy = true
  }
}
