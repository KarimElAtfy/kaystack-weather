# 1. Bootstrap applied by hand, in Italy North

Date: 2026-10-16

## Context

The state storage, the key vault and the identities GitHub signs in with have to exist before CI can do anything, so CI can't be the one creating them. I also don't want CI to be able to change its own identities or the roles they hold. Everything goes in Italy North: it's the closest region and Flex Consumption is available there. Static Web Apps can't be created in Italy North, so the site goes to West Europe. Its content is served from everywhere anyway.

## Decision

The resources everything else depends on live in `infra/bootstrap`: state storage, the Key Vault, the three CI identities and their roles, the Defender plans, the location policy, budgets and the cost anomaly alert. I apply them from my PC, one step at a time, and CI never applies them. The first applies ran on a local state, because the account that holds it didn't exist yet. That state was encrypted and moved to Azure as soon as the keys existed.

All resources are in Italy North except the Static Web App, which is in West Europe. An "Allowed locations" policy on the three resource groups admits only these two regions. ADR 7 moved the Static Web App to East US 2.

## Consequences

A bootstrap change is a commit plus a manual `tofu apply`, so for a short time the repo and Azure can differ.

The plan identity can't read the bootstrap state, so drift there only shows up when I run a plan myself.
