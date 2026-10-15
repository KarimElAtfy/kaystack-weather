locals {
  location           = "italynorth"
  state_account_name = "stkaystackmeteostate"
  key_vault_name     = "kv-kaystack-meteo"
  repo               = "KarimElAtfy/meteo"

  tags = {
    project    = "meteo"
    managed-by = "opentofu"
    repo       = "github.com/${local.repo}"
  }
}

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

resource "azurerm_resource_group" "shared" {
  name     = "rg-meteo-shared"
  location = local.location
  tags     = merge(local.tags, { env = "shared" })
}

# Created empty here so identities, policy and budgets can be scoped to them
# before the main stack exists.
resource "azurerm_resource_group" "env" {
  for_each = toset(["prod", "dev"])

  name     = "rg-meteo-${each.key}"
  location = local.location
  tags     = merge(local.tags, { env = each.key })
}
