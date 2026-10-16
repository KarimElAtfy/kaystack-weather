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

  # The repository's tokens carry the owner and repository ids in the subject
  # (use_immutable_subject), so a renamed or recreated repo with the same name
  # can't match these credentials.
  github_subject = "repo:KarimElAtfy@255750400/kaystack-weather@1421413677"
}

resource "azurerm_federated_identity_credential" "plan_pull_request" {
  name                      = "github-pull-request"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["plan"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "${local.github_subject}:pull_request"
}

resource "azurerm_federated_identity_credential" "plan_main" {
  name                      = "github-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["plan"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "${local.github_subject}:ref:refs/heads/main"

  # Entra answers 409 to concurrent credential writes on the same identity.
  depends_on = [azurerm_federated_identity_credential.plan_pull_request]
}

resource "azurerm_federated_identity_credential" "apply_prod" {
  name                      = "github-env-prod"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["apply"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "${local.github_subject}:environment:prod"
}

resource "azurerm_federated_identity_credential" "deploy_release" {
  name                      = "github-env-release"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci["deploy"].id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "${local.github_subject}:environment:release"
}
