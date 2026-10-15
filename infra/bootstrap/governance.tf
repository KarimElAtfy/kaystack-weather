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
