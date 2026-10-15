data "azurerm_role_definition" "delegable" {
  for_each = toset([
    "Key Vault Secrets User",
    "Monitoring Metrics Publisher",
    "Storage Account Contributor",
    "Storage Blob Data Contributor",
    "Storage Blob Data Owner",
    "Website Contributor",
  ])

  name = each.key
}

locals {
  owner_object_id = data.azurerm_client_config.current.object_id

  # Passed to the condition so apply can never grant a role to itself, to plan or to deploy.
  ci_principal_ids = join(", ", [for identity in azurerm_user_assigned_identity.ci : identity.principal_id])

  # A condition can restrict which roles apply assigns, but not the resource it
  # assigns them on. Storage Account Contributor only on the public account and
  # Website Contributor only on the Function are left to the main stack.
  prod_delegable = [
    "Monitoring Metrics Publisher",
    "Storage Account Contributor",
    "Storage Blob Data Contributor",
    "Storage Blob Data Owner",
    "Website Contributor",
  ]
}

resource "azurerm_role_assignment" "owner_vault" {
  for_each = toset(["Key Vault Crypto Officer", "Key Vault Secrets Officer"])

  scope                = azurerm_key_vault.main.id
  role_definition_name = each.key
  principal_id         = local.owner_object_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "owner_state" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.owner_object_id
  principal_type       = "User"
}

resource "azurerm_role_definition" "plan_reader" {
  name        = "Meteo plan reader"
  scope       = azurerm_resource_group.env["prod"].id
  description = "Reader plus the list calls azurerm makes when it refreshes a Flex Consumption app and a Static Web App."

  permissions {
    actions = [
      "*/read",
      "Microsoft.Web/sites/config/list/Action",
      "Microsoft.Web/staticSites/listappsettings/Action",
      "Microsoft.Web/staticSites/listsecrets/action",
    ]
  }

  assignable_scopes = [azurerm_resource_group.env["prod"].id]
}

resource "azurerm_role_definition" "deployer" {
  name        = "Meteo deployer"
  scope       = azurerm_resource_group.env["prod"].id
  description = "Publish the Function package and read the Static Web App deployment token."

  permissions {
    actions = [
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Web/serverfarms/read",
      "Microsoft.Web/sites/publish/Action",
      "Microsoft.Web/sites/read",
      "Microsoft.Web/staticSites/listsecrets/action",
      "Microsoft.Web/staticSites/read",
    ]
  }

  assignable_scopes = [azurerm_resource_group.env["prod"].id]
}

resource "azurerm_role_assignment" "plan_prod" {
  scope              = azurerm_resource_group.env["prod"].id
  role_definition_id = azurerm_role_definition.plan_reader.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.ci["plan"].principal_id
  principal_type     = "ServicePrincipal"
}

# The main stack will assign Key Vault Secrets User on the ARPA secret, and
# refreshing that assignment needs read access on the vault.
resource "azurerm_role_assignment" "plan_vault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.ci["plan"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "plan_state" {
  scope                = azurerm_storage_container.state["prod"].id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.ci["plan"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "plan_state_key" {
  scope                = azurerm_key_vault_key.state["prod"].resource_versionless_id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = azurerm_user_assigned_identity.ci["plan"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "apply_prod" {
  scope                = azurerm_resource_group.env["prod"].id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.ci["apply"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "apply_prod_delegation" {
  scope                = azurerm_resource_group.env["prod"].id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.ci["apply"].principal_id
  principal_type       = "ServicePrincipal"
  condition_version    = "2.0"
  condition = templatefile("${path.module}/role-delegation.tftpl", {
    roles    = join(", ", [for role in local.prod_delegable : data.azurerm_role_definition.delegable[role].role_definition_id])
    excluded = local.ci_principal_ids
  })
}

# Meant for the ARPA secret only, but the secret is created by hand in M1 and a
# role assignment cannot target a scope that does not exist yet. On this vault
# Secrets User can read secrets only; it gives no access to the state keys.
resource "azurerm_role_assignment" "apply_vault_delegation" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.ci["apply"].principal_id
  principal_type       = "ServicePrincipal"
  condition_version    = "2.0"
  condition = templatefile("${path.module}/role-delegation.tftpl", {
    roles    = data.azurerm_role_definition.delegable["Key Vault Secrets User"].role_definition_id
    excluded = local.ci_principal_ids
  })
}

resource "azurerm_role_assignment" "apply_state" {
  scope                = azurerm_storage_container.state["prod"].id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ci["apply"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "apply_state_key" {
  scope                = azurerm_key_vault_key.state["prod"].resource_versionless_id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = azurerm_user_assigned_identity.ci["apply"].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "deploy_prod" {
  scope              = azurerm_resource_group.env["prod"].id
  role_definition_id = azurerm_role_definition.deployer.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.ci["deploy"].principal_id
  principal_type     = "ServicePrincipal"
}
