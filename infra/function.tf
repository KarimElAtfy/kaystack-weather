locals {
  # Until the secret exists the ARPA job asks Socrata without a token, under the
  # shared rate limit.
  arpa_token_setting = var.arpa_secret_set ? {
    ARPA_APP_TOKEN = "@Microsoft.KeyVault(SecretUri=${data.azurerm_key_vault.shared.vault_uri}secrets/arpa-app-token/)"
  } : {}
}

resource "azurerm_service_plan" "func" {
  #checkov:skip=CKV_AZURE_212:Flex Consumption scales to zero, and one instance at most is the cost ceiling
  #checkov:skip=CKV_AZURE_225:one instance by design; a missed timer run shows up in the hourly freshness check
  name                = "asp-meteo-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = local.tags
}

resource "azurerm_function_app_flex_consumption" "main" {
  name                = "func-kaystack-meteo-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  service_plan_id     = azurerm_service_plan.func.id

  runtime_name           = "python"
  runtime_version        = "3.13"
  instance_memory_in_mb  = 512
  maximum_instance_count = 1

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${module.func.primary_blob_endpoint}app-package"
  storage_authentication_type = "SystemAssignedIdentity"

  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = merge({
    # With identity storage azurerm still writes AzureWebJobsStorage, as a
    # connection string with an empty key, and filters that exact name out
    # when it reads the settings back. This lowercase entry replaces it on
    # write and survives the read; the host matches names regardless of case,
    # finds the value empty and uses the identity settings instead.
    azurewebjobsstorage              = ""
    AzureWebJobsStorage__accountName = module.func.name

    APPLICATIONINSIGHTS_AUTHENTICATION_STRING = "Authorization=AAD"

    LAKE_ACCOUNT   = module.lake.name
    PUBLIC_ACCOUNT = module.public.name
    RADAR_ORIGIN   = "https://weather.kaystack.dev"
    TIMERS_ENABLED = tostring(var.timers_enabled)
    USER_AGENT     = "weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather"
  }, local.arpa_token_setting)

  tags = local.tags

  # The endpoint above only depends on the account, not on the container.
  depends_on = [module.func]
}
