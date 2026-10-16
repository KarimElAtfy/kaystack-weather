locals {
  tags = {
    project    = "meteo"
    managed-by = "opentofu"
    repo       = "github.com/KarimElAtfy/meteo"
    env        = var.environment
  }
}

data "azurerm_resource_group" "env" {
  name = "rg-meteo-${var.environment}"
}

data "azurerm_key_vault" "shared" {
  name                = "kv-kaystack-meteo"
  resource_group_name = "rg-meteo-shared"
}

# The bootstrap owns this group so that the owner's address is never handed to
# GitHub. Dev alerts mail through it too.
data "azurerm_monitor_action_group" "owner" {
  name                = "ag-meteo-owner"
  resource_group_name = "rg-meteo-prod"
}
