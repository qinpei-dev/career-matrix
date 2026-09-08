$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

try {
    $composeConfig = docker compose config --format json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve the Compose volume name."
    }
    $volumeName = $composeConfig.volumes.postgres_data.name

    Write-Host "==> Stop Docker Compose services" -ForegroundColor Cyan
    docker compose down
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose down failed with exit code $LASTEXITCODE."
    }

    docker volume inspect $volumeName *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "==> Containers removed; $volumeName is preserved." -ForegroundColor Green
    }
    else {
        Write-Host "==> Containers removed; the local data volume does not exist yet." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Local environment shutdown failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
