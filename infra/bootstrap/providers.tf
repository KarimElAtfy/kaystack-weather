provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  resource_providers_to_register = [
    "Microsoft.AlertsManagement",
    "Microsoft.Automation",
    "Microsoft.Consumption",
    "Microsoft.CostManagement",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.ManagedIdentity",
    "Microsoft.OperationalInsights",
    "Microsoft.ResourceHealth",
    "Microsoft.Security",
    "Microsoft.Storage",
    "Microsoft.Web",
  ]

  features {
    key_vault {
      # Purge protection is on, so purging on destroy could only fail.
      purge_soft_delete_on_destroy       = false
      purge_soft_deleted_keys_on_destroy = false
    }
  }
}
