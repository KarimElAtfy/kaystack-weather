resource "azurerm_automation_account" "breaker" {
  #checkov:skip=CKV2_AZURE_24:the action group calls the webhook on the public endpoint
  name                = "aa-meteo-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  sku_name            = "Basic"

  # A webhook start counts as local authentication. Turning it off would leave
  # the alerts with nothing to call.
  local_authentication_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

# PowerShell 5.1: a PowerShell 7 runbook receives the webhook body as invalid JSON.
resource "azurerm_automation_runbook" "breaker" {
  name                    = "breaker"
  resource_group_name     = data.azurerm_resource_group.env.name
  location                = data.azurerm_resource_group.env.location
  automation_account_name = azurerm_automation_account.breaker.name
  runbook_type            = "PowerShell"
  log_progress            = false
  log_verbose             = false
  content                 = file("${path.module}/breaker.ps1")
  tags                    = local.tags
}

resource "azurerm_automation_webhook" "breaker" {
  name                    = "metric-alerts"
  resource_group_name     = data.azurerm_resource_group.env.name
  automation_account_name = azurerm_automation_account.breaker.name
  runbook_name            = azurerm_automation_runbook.breaker.name

  # Ten years is the longest a webhook can live. After this date the alerts
  # still mail the owner, but nothing gets closed or stopped.
  expiry_time = "2036-06-30T00:00:00Z"
}

resource "azurerm_monitor_action_group" "breaker" {
  count = var.breaker_alerts ? 1 : 0

  name                = "ag-meteo-breaker"
  resource_group_name = data.azurerm_resource_group.env.name
  short_name          = "breaker"

  automation_runbook_receiver {
    name                    = "breaker"
    automation_account_id   = azurerm_automation_account.breaker.id
    runbook_name            = azurerm_automation_runbook.breaker.name
    webhook_resource_id     = azurerm_automation_webhook.breaker.id
    is_global_runbook       = false
    service_uri             = azurerm_automation_webhook.breaker.uri
    use_common_alert_schema = true
  }

  tags = local.tags
}

locals {
  public_account = {
    scope     = module.public.id
    namespace = "Microsoft.Storage/storageAccounts"
  }
  function_app = {
    scope     = azurerm_function_app_flex_consumption.main.id
    namespace = "Microsoft.Web/sites"
  }

  # OnDemandFunctionExecutionUnits counts MB-milliseconds: GB-s x 1,024,000.
  spend_limits = {
    public-egress-1h       = merge(local.public_account, { metric = "Egress", threshold = 1000000000, frequency = "PT15M", window = "PT1H" })
    public-egress-1d       = merge(local.public_account, { metric = "Egress", threshold = 3000000000, frequency = "PT1H", window = "P1D" })
    public-transactions-1h = merge(local.public_account, { metric = "Transactions", threshold = 20000, frequency = "PT15M", window = "PT1H" })
    public-transactions-1d = merge(local.public_account, { metric = "Transactions", threshold = 100000, frequency = "PT1H", window = "P1D" })
    function-compute-6h    = merge(local.function_app, { metric = "OnDemandFunctionExecutionUnits", threshold = 1600 * 1024000, frequency = "PT1H", window = "PT6H" })
    function-compute-1d    = merge(local.function_app, { metric = "OnDemandFunctionExecutionUnits", threshold = 5000 * 1024000, frequency = "PT1H", window = "P1D" })
  }
}

resource "azurerm_monitor_metric_alert" "breaker" {
  for_each = var.breaker_alerts ? local.spend_limits : {}

  name                = "breaker-${each.key}"
  resource_group_name = data.azurerm_resource_group.env.name
  scopes              = [each.value.scope]
  severity            = 1
  frequency           = each.value.frequency
  window_size         = each.value.window

  criteria {
    metric_namespace = each.value.namespace
    metric_name      = each.value.metric
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = each.value.threshold
  }

  action {
    action_group_id = azurerm_monitor_action_group.breaker[0].id
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.owner.id
  }

  tags = local.tags
}
