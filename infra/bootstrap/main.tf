locals {
  location = "italynorth"
  repo     = "KarimElAtfy/meteo"

  tags = {
    project    = "meteo"
    managed-by = "opentofu"
    repo       = "github.com/${local.repo}"
  }
}

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
