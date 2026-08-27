<#
.SYNOPSIS
    Trusts the staging Caddy container's internal root CA on this Windows host.

.DESCRIPTION
    docker-compose.staging.yml's Caddyfile uses `tls internal` (Caddy's own
    local CA, not a public ACME issuer -- see the comment at the top of
    infra/caddy/Caddyfile for why). Caddy generates that CA itself, inside
    the `staging_caddy_data` volume, the first time the container starts.
    Chrome/curl on the Windows host don't know about it by default, which is
    what produces ERR_CERT_AUTHORITY_INVALID for https://*.lvh.me.

    This script:
      1. Copies ONLY the public root certificate (root.crt) out of the
         running caddy container -- never root.key or intermediate.key.
      2. Imports it into the CURRENT USER's Trusted Root Certification
         Authorities store (Cert:\CurrentUser\Root), which Chrome/Edge/curl
         on Windows all consult. No admin elevation is required for this
         store, which is the least-privileged way to get there.
      3. If the CA was regenerated (e.g. the staging_caddy_data volume was
         recreated), removes the old, now-stale entry for the same CA
         subject before importing the new one, so re-running this script
         after a volume reset is always safe to repeat.

    This only affects trust for the local staging preview. It does not
    touch the Caddyfile, docker-compose.staging.yml, or any production TLS
    configuration.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File infra\caddy\trust-local-ca.ps1
#>

$ErrorActionPreference = "Stop"

# Docker itself runs inside WSL2 on this host (there is no native docker.exe
# on the Windows PATH) -- every docker call here is routed through wsl.exe.
# Matched by container name rather than `docker compose ps` so this doesn't
# depend on being invoked from a directory where compose can resolve its
# .env / project name -- any container whose compose service is "caddy" is
# named "<project>-caddy-<n>" or "<project>_caddy_<n>" by Compose's own
# convention, so a name filter is a robust, context-free way to find it.
$OutCert = Join-Path $PSScriptRoot "caddy-local-root-ca.crt"
$SubjectMatch = "*Caddy Local Authority*"

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    throw "wsl.exe not found -- this host's docker runs inside WSL2 and this script relies on it."
}

Write-Output "Locating the running staging caddy container (via WSL2 docker)..."
$containerId = (wsl -- bash -c "docker ps --filter 'name=caddy' --format '{{.ID}}'" 2>$null | Select-Object -First 1)
if (-not $containerId) {
    throw "No running container matching name 'caddy' found. Start the staging stack first (docker compose -f docker-compose.staging.yml up -d)."
}
$containerName = (wsl -- bash -c "docker inspect --format '{{.Name}}' $containerId" 2>$null).Trim() -replace '^/', ''
Write-Output "Found container: $containerName"

Write-Output "Exporting ONLY the public root CA cert (root.crt) -- no private keys..."
$certPem = wsl -- bash -c "docker exec $containerId cat /data/caddy/pki/authorities/local/root.crt" 2>$null
if (-not $certPem) {
    throw "Failed to export root.crt from $containerName. Has the caddy container generated its CA yet? (It does so on first start.)"
}
Set-Content -Path $OutCert -Value $certPem -Encoding ascii
if (-not (Test-Path $OutCert) -or (Get-Item $OutCert).Length -eq 0) {
    throw "Failed to write $OutCert."
}

$newCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($OutCert)
Write-Output "Exported CA: $($newCert.Subject) (thumbprint $($newCert.Thumbprint), expires $($newCert.NotAfter))"

$stale = Get-ChildItem -Path Cert:\CurrentUser\Root | Where-Object {
    $_.Subject -like $SubjectMatch -and $_.Thumbprint -ne $newCert.Thumbprint
}
foreach ($old in $stale) {
    Write-Output "Removing stale/regenerated CA entry: $($old.Thumbprint)"
    Remove-Item -Path "Cert:\CurrentUser\Root\$($old.Thumbprint)" -Confirm:$false -Force
}

$already = Get-ChildItem -Path Cert:\CurrentUser\Root | Where-Object { $_.Thumbprint -eq $newCert.Thumbprint }
if ($already) {
    Write-Output "Already trusted -- nothing to do."
} else {
    Write-Output "Importing into CurrentUser Trusted Root Certification Authorities store..."
    certutil -user -addstore Root $OutCert | Out-Null
    Write-Output "Imported."
}

Write-Output ""
Write-Output "Verifying no private key is present in the trust store entry..."
$installed = Get-ChildItem -Path Cert:\CurrentUser\Root | Where-Object { $_.Thumbprint -eq $newCert.Thumbprint }
Write-Output "HasPrivateKey: $($installed.HasPrivateKey)  (must be False)"

Write-Output ""
Write-Output "Done. Verify in Chrome: https://admin.lvh.me, https://dashboard.lvh.me,"
Write-Output "https://demo-store-a.lvh.me, https://demo-store-b.lvh.me should all load"
Write-Output "without ERR_CERT_AUTHORITY_INVALID. Restart Chrome first if it was already"
Write-Output "running -- it caches certificate validation results per-process."
