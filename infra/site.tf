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
