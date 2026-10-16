# 2. OpenTofu state encrypted client side with Key Vault keys

Date: 2026-10-16

## Context

The state is more sensitive than it looks. From M1 it will hold the Static Web App deployment token, because azurerm always writes it there, and it already has some attributes of the storage keys. Entra-only access protects the storage account, but anyone with read access on a container would still see that state in clear text. With client-side encryption they also need the key in Key Vault, which is a separate grant. This is one of the reasons I picked OpenTofu over Terraform.

## Decision

OpenTofu encrypts every state and plan file itself (`azure_vault` key provider, AES-GCM) before writing it, and refuses to write plaintext. Each state has its own RSA key in `kv-kaystack-meteo`: `tfstate-bootstrap`, `tfstate-prod` and `tfstate-dev`.

The states live in `stkaystackmeteostate`, one container per state. The account is zone-redundant and accepts Entra sign-in only. It keeps every version of every blob, keeps deleted blobs and containers for 30 days, and has a delete lock. The vault has purge protection. The three keys are also backed up outside Azure.

## Consequences

Reading a state takes two grants: a data role on its container and Crypto User on its key. The plan identity has both for prod and nothing for bootstrap or dev.

Every OpenTofu run calls Key Vault. In the environment root the key name comes from `var.environment`, so `init`, `plan`, `show` and `output` all need `-var-file`.

Losing the keys means losing every state. Purge protection and the key backups are there for that.
