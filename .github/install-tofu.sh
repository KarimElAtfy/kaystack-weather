#!/usr/bin/env bash
# The one place the CI version of OpenTofu is pinned; every workflow that runs
# tofu calls this script.
set -euo pipefail

version=1.13.1
sha256=8ccbc6f8ee21d2827715f3c6e08a9b3e0209b1e62057c05067ef117e047c1a80

curl -fsSLo /tmp/tofu.zip "https://github.com/opentofu/opentofu/releases/download/v${version}/tofu_${version}_linux_amd64.zip"
echo "${sha256}  /tmp/tofu.zip" | sha256sum -c -
sudo unzip -o -q /tmp/tofu.zip tofu -d /usr/local/bin
tofu version
