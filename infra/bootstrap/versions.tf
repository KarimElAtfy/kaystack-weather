terraform {
  required_version = "~> 1.13.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9.0"
    }
  }

  backend "azurerm" {
    storage_account_name = local.state_account_name
    container_name       = "bootstrap"
    key                  = "bootstrap.tfstate"
    use_azuread_auth     = true
  }

  encryption {
    key_provider "azure_vault" "state" {
      vault_uri      = "https://${local.key_vault_name}.vault.azure.net"
      vault_key_name = "tfstate-bootstrap"
      key_length     = 32
    }

    method "aes_gcm" "state" {
      keys = key_provider.azure_vault.state
    }

    method "unencrypted" "migrate" {}

    state {
      method = method.aes_gcm.state

      fallback {
        method = method.unencrypted.migrate
      }
    }

    plan {
      method = method.aes_gcm.state

      fallback {
        method = method.unencrypted.migrate
      }
    }
  }
}
