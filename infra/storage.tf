module "lake" {
  source = "./modules/storage"

  name                = "stkaystackmeteolake${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  containers          = ["raw", "curated", "forecasts", "legacy"]
  soft_delete_days    = 30
  prevent_destroy     = var.environment == "prod"
  tags                = local.tags
}

module "public" {
  #checkov:skip=CKV_AZURE_190:this account exists to serve the site's JSON and radar frames to anyone
  #checkov:skip=CKV2_AZURE_47:the same account switch as CKV_AZURE_190, and the one the breaker turns off
  #checkov:skip=CKV_AZURE_34:blob level only, so files are read by name and the container cannot be listed
  source = "./modules/storage"

  name                = "stkaystackmeteopub${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  containers          = ["public"]
  anonymous_read      = true
  cors_origins        = ["https://weather.kaystack.dev"]
  prevent_destroy     = false
  tags                = local.tags
}

# Host locks, timer state and the deployment package.
module "func" {
  source = "./modules/storage"

  name                = "stkaystackmeteofunc${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  location            = data.azurerm_resource_group.env.location
  containers          = ["app-package"]
  prevent_destroy     = false
  tags                = local.tags
}

# Every deterministic value is kept in curated and the ensembles are summarised
# there. 90 days leaves time to rebuild a summary after a bug.
resource "azurerm_storage_management_policy" "lake" {
  storage_account_id = module.lake.id

  rule {
    name    = "openmeteoraw"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["raw/open-meteo/"]
    }

    actions {
      base_blob {
        delete_after_days_since_creation_greater_than = 90
      }
    }
  }
}

# Unlocked, so the period can still be shortened or the policy removed. Until
# then a blob here cannot be overwritten or deleted, so every name carries its
# issue time.
resource "azurerm_storage_container_immutability_policy" "lake" {
  for_each = var.immutable_days > 0 ? toset(["forecasts", "legacy"]) : toset([])

  storage_container_resource_manager_id = module.lake.container_ids[each.key]
  immutability_period_in_days           = var.immutable_days
}
