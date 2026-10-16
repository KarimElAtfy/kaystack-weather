terraform {
  required_version = "~> 1.13.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9.0"
    }
  }

  backend "azurerm" {}

  encryption {
    key_provider "azure_vault" "state" {
      vault_uri      = "https://kv-kaystack-meteo.vault.azure.net"
      vault_key_name = "tfstate-${var.environment}"
      key_length     = 32

      # Unlike the backend and the provider, this key provider does not read
      # ARM_USE_OIDC. Outside Actions the OIDC check fails and it falls back
      # to the az CLI login.
      use_oidc = true
    }

    method "aes_gcm" "state" {
      keys = key_provider.azure_vault.state
    }

    state {
      method   = method.aes_gcm.state
      enforced = true
    }

    plan {
      method   = method.aes_gcm.state
      enforced = true
    }
  }
}
