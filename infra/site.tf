resource "azurerm_static_web_app" "site" {
  name                = "stapp-meteo-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  # Static sites are offered in five regions, Italy North is not one of them,
  # and West Europe refused this subscription on 2026-10-20 (ADR 7). The region
  # holds only the app's settings; the files are served from the global edge.
  location = "eastus2"
  sku_tier = "Free"
  sku_size = "Free"

  # deploy.yml uploads the build with the deployment token, so the app has no
  # repository link, and a public repo must not get pull request environments.
  preview_environments_enabled       = false
  configuration_file_changes_enabled = true

  tags = local.tags
}

# With cname-delegation the platform checks, while the domain is being added,
# that its CNAME already points at the default host name, so the record at the
# registrar has to exist before this is applied.
resource "azurerm_static_web_app_custom_domain" "site" {
  count = var.site_domain == null ? 0 : 1

  static_web_app_id = azurerm_static_web_app.site.id
  domain_name       = var.site_domain
  validation_type   = "cname-delegation"

  # The API does not return validation_type, so after the import of
  # 2026-10-20 every plan would replace the domain to set it again.
  lifecycle {
    ignore_changes = [validation_type]
  }
}
