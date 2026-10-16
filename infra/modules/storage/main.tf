terraform {
  required_version = "~> 1.13.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.9.0"
    }
  }
}

# tflint-ignore: azurerm_resources_missing_prevent_destroy # set by the caller, true only for the prod lake
resource "azurerm_storage_account" "this" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = var.anonymous_read
  local_user_enabled              = false

  blob_properties {
    dynamic "delete_retention_policy" {
      for_each = var.soft_delete_days > 0 ? [var.soft_delete_days] : []
      content {
        days = delete_retention_policy.value
      }
    }

    dynamic "container_delete_retention_policy" {
      for_each = var.soft_delete_days > 0 ? [var.soft_delete_days] : []
      content {
        days = container_delete_retention_policy.value
      }
    }

    # The site sends plain GET and HEAD, which need no preflight. azurerm wants
    # one entry in each header list: any request header, and ETag, the one useful
    # response header a browser does not expose by default.
    dynamic "cors_rule" {
      for_each = length(var.cors_origins) > 0 ? [var.cors_origins] : []
      content {
        allowed_origins    = cors_rule.value
        allowed_methods    = ["GET", "HEAD"]
        allowed_headers    = ["*"]
        exposed_headers    = ["ETag"]
        max_age_in_seconds = 3600
      }
    }
  }

  tags = var.tags

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

resource "azurerm_storage_container" "this" {
  for_each = toset(var.containers)

  name                  = each.key
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = var.anonymous_read ? "blob" : "private"

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}
