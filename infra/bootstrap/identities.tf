resource "azurerm_user_assigned_identity" "ci" {
  for_each = toset(["plan", "apply", "deploy"])

  name                = "id-meteo-${each.key}"
  location            = local.location
  resource_group_name = azurerm_resource_group.shared.name
  tags                = local.tags
}

locals {
  github_issuer   = "https://token.actions.githubusercontent.com"
  github_audience = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "plan_pull_request" {
  name                      = "github-pull-request"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["plan"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${local.repo}:pull_request"
}

resource "azurerm_federated_identity_credential" "plan_main" {
  name                      = "github-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["plan"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${local.repo}:ref:refs/heads/main"

  # Entra answers 409 to concurrent credential writes on the same identity.
  depends_on = [azurerm_federated_identity_credential.plan_pull_request]
}

resource "azurerm_federated_identity_credential" "apply_prod" {
  name                      = "github-env-prod"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["apply"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${local.repo}:environment:prod"
}

resource "azurerm_federated_identity_credential" "deploy_release" {
  name                      = "github-env-release"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["deploy"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${local.repo}:environment:release"
}
