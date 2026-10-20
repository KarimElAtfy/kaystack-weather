resource "azurerm_static_web_app" "site" {
  name                = "stapp-meteo-${var.environment}"
  resource_group_name = data.azurerm_resource_group.env.name
  # Microsoft.Web offers static sites in five regions and Italy North is not
  # one of them. The files are served from the global edge either way.
  location = "westeurope"
  sku_tier = "Free"
  sku_size = "Free"

  # deploy.yml uploads the build with the deployment token, so the app has no
  # repository link, and a public repo must not get pull request environments.
  preview_environments_enabled       = false
  configuration_file_changes_enabled = true

  tags = local.tags
}
