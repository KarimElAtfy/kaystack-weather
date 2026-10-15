# A trial started from a portal prompt bills automatically after 30 days.
# Keeping every plan at Free in code means the weekly drift check catches it.
resource "azurerm_security_center_subscription_pricing" "free" {
  for_each = toset([
    "AI",
    "Api",
    "AppServices",
    "Arm",
    "CloudPosture",
    "Containers",
    "CosmosDbs",
    "KeyVaults",
    "OpenSourceRelationalDatabases",
    "SqlServerVirtualMachines",
    "SqlServers",
    "StorageAccounts",
    "VirtualMachines",
  ])

  resource_type = each.key
  tier          = "Free"
}

data "azurerm_policy_definition" "allowed_locations" {
  display_name = "Allowed locations"
}

resource "azurerm_resource_group_policy_assignment" "allowed_locations" {
  for_each = {
    shared = azurerm_resource_group.shared.id
    prod   = azurerm_resource_group.env["prod"].id
    dev    = azurerm_resource_group.env["dev"].id
  }

  name                 = "allowed-locations"
  resource_group_id    = each.value
  policy_definition_id = data.azurerm_policy_definition.allowed_locations.id

  # The Static Web App is the one resource outside Italy North.
  parameters = jsonencode({
    listOfAllowedLocations = { value = ["italynorth", "westeurope"] }
  })
}
