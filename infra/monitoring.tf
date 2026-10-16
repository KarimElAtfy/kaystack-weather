resource "azurerm_log_analytics_workspace" "main" {
  name                         = "log-meteo-${var.environment}"
  resource_group_name          = data.azurerm_resource_group.env.name
  location                     = data.azurerm_resource_group.env.location
  sku                          = "PerGB2018"
  retention_in_days            = 30
  daily_quota_gb               = var.log_daily_cap_gb
  local_authentication_enabled = false
  tags                         = local.tags
}

resource "azurerm_application_insights" "main" {
  name                         = "appi-meteo-${var.environment}"
  resource_group_name          = data.azurerm_resource_group.env.name
  location                     = data.azurerm_resource_group.env.location
  workspace_id                 = azurerm_log_analytics_workspace.main.id
  application_type             = "other"
  retention_in_days            = 30
  daily_data_cap_in_gb         = var.log_daily_cap_gb
  local_authentication_enabled = false
  tags                         = local.tags
}

# Every timer run is a request in Application Insights. The hourly job also
# fails on purpose when a source is older than its threshold.
resource "azurerm_monitor_metric_alert" "failed_runs" {
  name                = "failed-runs-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  scopes              = [azurerm_application_insights.main.id]
  severity            = 2
  frequency           = "PT15M"
  window_size         = "PT1H"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.owner.id
  }

  tags = local.tags
}

resource "azurerm_monitor_activity_log_alert" "function_stopped" {
  name                = "function-stopped-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = "global"
  scopes              = [azurerm_function_app_flex_consumption.main.id]
  description         = "The Function was stopped, by the breaker or by hand."

  criteria {
    category       = "Administrative"
    operation_name = "Microsoft.Web/sites/stop/action"
    status         = "Succeeded"
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.owner.id
  }

  tags = local.tags
}

# Applies that touch a storage account fire it as well. Kept that way so that no
# change to anonymous access goes unseen, whoever made it.
resource "azurerm_monitor_activity_log_alert" "storage_changed" {
  name                = "storage-changed-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = "global"
  scopes              = [data.azurerm_resource_group.env.id]
  description         = "A storage account in this resource group was changed."

  criteria {
    category       = "Administrative"
    operation_name = "Microsoft.Storage/storageAccounts/write"
    status         = "Succeeded"
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.owner.id
  }

  tags = local.tags
}

resource "azurerm_monitor_activity_log_alert" "function_health" {
  name                = "function-health-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = "global"
  scopes              = [azurerm_function_app_flex_consumption.main.id]
  description         = "Azure reports the Function as degraded or unavailable."

  criteria {
    category = "ResourceHealth"

    resource_health {
      current  = ["Degraded", "Unavailable"]
      previous = ["Available"]
      reason   = ["PlatformInitiated", "Unknown"]
    }
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.owner.id
  }

  tags = local.tags
}
