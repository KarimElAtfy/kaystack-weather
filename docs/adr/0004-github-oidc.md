# 4. GitHub OIDC with three identities and no stored secrets

Date: 2026-10-16

## Context

CI needs Azure to plan and, later, to deploy. A client secret stored in GitHub would be one more thing that can leak and that I'd have to rotate. With OIDC each job gets a short-lived token from GitHub and Entra checks where it comes from before handing out access. One identity for everything would give a pull request job the same rights as a deploy, so each kind of job has its own identity with only what it needs.

## Decision

GitHub Actions signs in to Azure with federated credentials. No secret is stored in GitHub. There are three user-assigned identities:

| Identity | Accepted subject | Rights |
| --- | --- | --- |
| `id-meteo-plan` | pull requests, `main` | read Azure and the prod state |
| `id-meteo-apply` | environment `prod`, which needs my approval and runs only from `main` | Contributor on `rg-meteo-prod`, role assignments under a condition |
| `id-meteo-deploy` | environment `release`, `main` only | publish the Function, read the Static Web App deployment token |

The condition on `apply`: it may hand out only five roles in `rg-meteo-prod` and Key Vault Secrets User on the vault, only to service principals, and never to the three CI identities themselves.

## Consequences

A pull request job can at most read. Its token subject is `pull_request`, and only `plan` trusts it. The [negative test](https://github.com/KarimElAtfy/meteo/actions/runs/38890574240) shows Entra refusing `apply` to a job outside `prod`.

Accepted risk: from M1 the plan identity can read the Static Web App deployment token, through `listsecrets` and through the prod state it decrypts. Only branches I push run with that identity, and fork pull requests get no OIDC token.

A condition can limit which roles are handed out but not on which resource, so that part is checked in review of the main stack.

The subjects carry the owner and repository ids as well as the names, because that is what GitHub sends for this repository. A recreated repository with the same name can't match them. Renaming the repository or the account means updating `github_subject` and applying the bootstrap again.
