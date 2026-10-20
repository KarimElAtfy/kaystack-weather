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

  # The Static Web App is the one resource outside Italy North. West Europe
  # stopped taking new customers, so it lives in East US 2 (ADR 7), and only
  # the resource groups that can hold it admit that region.
  parameters = jsonencode({
    listOfAllowedLocations = {
      value = each.key == "shared" ? ["italynorth", "westeurope"] : ["italynorth", "westeurope", "eastus2"]
    }
  })
}

locals {
  # A budget must start on the first day of the current month, and changing
  # the start date replaces the budget, hence ignore_changes below.
  budget_start = formatdate("YYYY-MM-'01T00:00:00Z'", timestamp())
}

resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "budget-meteo"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 3
  time_grain      = "Monthly"

  time_period {
    start_date = local.budget_start
  }

  dynamic "notification" {
    for_each = [
      { threshold = 50, type = "Actual" },
      { threshold = 80, type = "Actual" },
      { threshold = 100, type = "Actual" },
      { threshold = 100, type = "Forecasted" },
    ]

    content {
      operator       = "GreaterThanOrEqualTo"
      threshold      = notification.value.threshold
      threshold_type = notification.value.type
      contact_emails = [var.alert_email]
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_consumption_budget_resource_group" "dev" {
  name              = "budget-meteo-dev"
  resource_group_id = azurerm_resource_group.env["dev"].id
  amount            = 1
  time_grain        = "Monthly"

  time_period {
    start_date = local.budget_start
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_cost_anomaly_alert" "subscription" {
  name            = "meteo-cost-anomaly"
  display_name    = "Meteo cost anomaly"
  subscription_id = data.azurerm_subscription.current.id
  email_subject   = "Cost anomaly on the meteo subscription"
  email_addresses = [var.alert_email]
}

# Alerts in the main stack find this group by name, so the address is set only
# here, from the owner's PC, and never passes through GitHub. Saving it sends a
# one-time passcode to the address, to be confirmed within 30 minutes.
resource "azurerm_monitor_action_group" "owner" {
  name                = "ag-meteo-owner"
  resource_group_name = azurerm_resource_group.env["prod"].name
  short_name          = "meteo"
  tags                = local.tags

  email_receiver {
    name                    = "owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}
