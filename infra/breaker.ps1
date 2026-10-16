param([object] $WebhookData)

# Started by the spend alerts with the common alert schema. A public account
# alert closes anonymous reads on that account, a Function alert stops the app.
$ErrorActionPreference = 'Stop'

$alert = (ConvertFrom-Json $WebhookData.RequestBody).data.essentials

# Stateful alerts call the action group again when they resolve.
if ($alert.monitorCondition -ne 'Fired') {
  Write-Output "$($alert.alertRule): $($alert.monitorCondition), nothing to do"
  return
}

$identity = Invoke-RestMethod -Method Get `
  -Uri "${env:IDENTITY_ENDPOINT}?resource=https://management.azure.com/" `
  -Headers @{ 'X-IDENTITY-HEADER' = $env:IDENTITY_HEADER; 'Metadata' = 'True' }
$headers = @{ Authorization = "Bearer $($identity.access_token)" }

foreach ($target in $alert.alertTargetIDs) {
  if ($target -match '/providers/microsoft\.storage/storageaccounts/[^/]+$') {
    Invoke-RestMethod -Method Patch -Headers $headers -ContentType 'application/json' `
      -Uri "https://management.azure.com${target}?api-version=2025-06-01" `
      -Body '{"properties":{"allowBlobPublicAccess":false}}' | Out-Null
    Write-Output "$($alert.alertRule): anonymous access closed on $target"
  }
  elseif ($target -match '/providers/microsoft\.web/sites/[^/]+$') {
    Invoke-RestMethod -Method Post -Headers $headers `
      -Uri "https://management.azure.com${target}/stop?api-version=2024-11-01" | Out-Null
    Write-Output "$($alert.alertRule): stopped $target"
  }
  else {
    throw "$($alert.alertRule): no action defined for $target"
  }
}
