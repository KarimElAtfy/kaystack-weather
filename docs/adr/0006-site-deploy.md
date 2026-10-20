# 6. Site uploaded with the Static Web Apps client, pinned by hash

Date: 2026-10-20

## Context

The site is a folder of prerendered files that has to reach the Static Web App from CI. Microsoft offers three ways to upload it, and all three end up running the same upload client, StaticSitesClient.

The `Azure/static-web-apps-deploy` action is a Docker image tagged `stable`, so it can't be pinned, and its commit would have to be added to the actions this repo allows. The SWA CLI is the documented way outside that action. Its `swa deploy` installs 376 npm packages into the job that holds the deployment token, then downloads StaticSitesClient and checks it only against a hash served from the same host as the file. Every other tool CI downloads here is pinned by version and checked against a SHA-256 written in the repo.

## Decision

The deploy job downloads StaticSitesClient by its build id and checks it against a SHA-256 in `deploy.yml`, the same way as OpenTofu, uv and the linters. It runs the client with the environment the SWA CLI 2.1.0 gives it: upload action, the build folder, no app build, the deployment token, and no environment name, which means production.

The site is built in its own job, without any token. The deploy job signs in as the deploy identity in `release`, reads the deployment token with `listsecrets` right before the upload, masks it, uploads, and then checks the headers the live site sends.

## Consequences

The job that holds the token runs one Microsoft binary that CI has checked, and nothing from npm.

The client's environment variables are not documented; they come from the SWA CLI's source. If Microsoft changes them, the upload fails instead of deploying something unexpected. The way back is the SWA CLI, pinned in a lock file of its own.

Moving to a newer client is a manual change of the build id and the hash, done with the monthly dependency updates.

The check after the upload covers what the documentation leaves open: whether the security headers, the closed `.auth` routes and the trailing-slash redirects behave as `staticwebapp.config.json` says.
