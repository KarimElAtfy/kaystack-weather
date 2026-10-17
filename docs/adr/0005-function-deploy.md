# 5. Function package built in CI, published without the az command

Date: 2026-10-17

## Context

The pipeline runs on a Flex Consumption Function App. Microsoft's usual path for Python is a remote build: upload the code with `requirements.txt` and let the platform install it. That build has a 60 second limit, and pip took 18 to 40 seconds for these dependencies in my tests. The documented deploy command, `az functionapp deployment source config-zip`, also lists the app settings before it deploys and reads the host keys afterwards, so the deploy identity would need both rights.

## Decision

The `package` job in `deploy.yml` installs the locked dependencies for Linux and Python 3.13 into `.python_packages` with uv, from the hashed `requirements.txt`, and zips them with the code and the town files. The `deploy` job signs in as the deploy identity, posts that zip to the Function's One Deploy endpoint with `RemoteBuild=false`, and polls the deployment the way az does.

## Consequences

The deploy identity only reads the site and publishes to it. The package holds the versions CI tested, and a deploy no longer depends on how fast pip runs on the platform. The zip is about 55 MB instead of a few hundred KB. If a dependency ever ships no Linux wheel, the remote build is the way back: `RemoteBuild=true` and no install step.
