# 7. Static Web App in East US 2

Date: 2026-10-20

## Context

Static Web Apps exist in five regions: Central US, East US 2, West US 2, West Europe and East Asia. ADR 1 put the site in West Europe, the only one in Europe. The first apply failed there: Azure refused the app with `RequestDisallowedByAzure`, because West Europe is currently not accepting new customers on this subscription. A support request might open it up, but nobody can say when, and the site would wait for it.

## Decision

The Static Web App goes to East US 2. Before changing anything I created a throwaway Free app there in a separate resource group, and it worked; the group was deleted right after.

The "Allowed locations" policy admits East US 2 on the prod and dev resource groups, where the app can live. The shared resource group keeps Italy North and West Europe only.

## Consequences

The region holds the app's configuration. The files people download are static and are served from the Static Web Apps edge, and the site has no backend and stores nothing about its visitors, so no personal data ends up in the United States because of this.

West Europe stays in the policy. If it opens up again, moving back is a one-line change, but it recreates the app with a new default host name, so the `weather` CNAME has to follow it.
