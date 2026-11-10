$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

try {
    $dataDirectory = Join-Path $projectRoot "data\postgres"

    Write-Host "==> Stop Docker Compose services" -ForegroundColor Cyan
    docker compose down
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose down failed with exit code $LASTEXITCODE."
    }

    if (Test-Path -LiteralPath (Join-Path $dataDirectory "PG_VERSION")) {
        Write-Host "==> Containers removed; database files in data\postgres are preserved." -ForegroundColor Green
    }
    else {
        Write-Host "==> Containers removed; the local database folder does not exist yet." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Local environment shutdown failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
