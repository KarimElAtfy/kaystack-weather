# kaystack-weather

Weather forecasts for Pedrengo and Sesto Calende, two towns in Lombardy, at https://weather.kaystack.dev. The site is a beta. Each forecast is made for a named ARPA station near the town, Torre Boldone for Pedrengo (3.4 km) and Ispra JRC for Sesto Calende (9.1 km), and the site says which.

How it works:

- An Azure Function collects on timers: DPC radar frames every five minutes, the METARs of Orio al Serio and Malpensa twice an hour, new runs of about ten models and their ensembles from Open-Meteo, DWD MOSMIX and the Yr point forecast every hour, and the ARPA Lombardia stations every three hours. Raw answers are written once and compacted every night into Parquet.
- Every hour each model's temperature is corrected by the bias it showed against the station over the last 60 days, and the corrected models are averaged (`pipeline/meteo/mos.py`). The other variables are the plain mean of the models. The coefficients are fitted again every night.
- The pipeline publishes small JSON files and radar sprites for the site. Their contract is `pipeline/meteo/contract.py`, and `schema/` holds the JSON Schema generated from it.
- The site is a static SvelteKit build on Azure Static Web Apps. It sets no cookies and makes no requests to third parties.

Layout:

- `infra/bootstrap` holds what the rest depends on: the OpenTofu state storage, the Key Vault whose keys encrypt that state, and the identities GitHub Actions signs in with through OIDC. It is applied by hand.
- `infra` is the root for the prod and dev environments, selected with `-backend-config` and `-var-file`. It holds the storage, the Function App, its logs and alerts, a breaker that closes public reads and stops the app if usage passes its limits, and the Static Web App.
- `pipeline` is the Python the Function runs. `python -m meteo` runs any of its jobs by hand.
- `site` is the website.
- `towns` describes the two towns: their reference stations, airports and radar view.
- `docs/time-conventions.md` says what each source's timestamps mean, `docs/verification.md` which forecasts may be scored and when, and `docs/adr` holds the decisions behind this setup, one short file each.
- `.github/workflows`: `ci.yml` checks every part on pull requests, `infra.yml` applies prod after approval, `deploy.yml` deploys the pipeline and the site, `freshness.yml` checks every hour from outside Azure that every source is recent, and `scheduled.yml` looks for drift and vulnerable dependencies every week.

## Cost

Measured over the first seven complete days of collection, 18 to 24 October 2026, from Azure Cost Management and the storage and Function metrics, then multiplied by 30/7. EUR before VAT.

| Line | Week | Month |
| --- | --- | --- |
| Function host storage | 0.096 | 0.41 |
| Public storage: status, site data, radar | 0.022 | 0.10 |
| Data lake | 0.014 | 0.06 |
| Key Vault and state | 0.002 | 0.01 |
| Total | 0.135 | 0.58 |

Compute, about 34,000 GB-s a month, and logs, about 0.14 GB a month, stay inside Azure's free grants. With VAT the month comes to about EUR 0.71.

## First week of data

On those seven days every radar frame, ARPA value, METAR, MOSMIX issue and Yr forecast was stored, checked against counts from the sources. Every deterministic model run Open-Meteo published is in the archive; some were first missed by the hourly job and fetched again from Open-Meteo's Single Runs. Five ensemble runs are missing and cannot be recovered, because Open-Meteo keeps no past ensemble runs: one ICON-CH1 and one ICON-CH2 run on 22 October, and three ECMWF IFS runs on 23 and 24 October. They fall where Open-Meteo published no deterministic run or cut the IFS ensemble to fewer runs a day, so they were probably never published.

MIT license.
