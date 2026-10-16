# meteo

Weather forecasts for Pedrengo and Sesto Calende, two towns in Lombardy. The site will be served at weather.kaystack.dev. Nothing is deployed yet.

What is here so far:

- `infra/bootstrap` holds what the rest depends on: the OpenTofu state storage, the Key Vault whose keys encrypt that state, and the identities GitHub Actions signs in with through OIDC. It is applied by hand.
- `infra` is the root for the prod and dev environments, selected with `-backend-config` and `-var-file`.
- `docs/adr` holds the decisions behind this setup, one short file each.

MIT license.
