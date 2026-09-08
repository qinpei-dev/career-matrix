param(
    [switch]$NoBuild,
    [switch]$NoSeed,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$dockerReady = $false

function Test-DockerEngine {
    param(
        [ValidateSet("version", "info")]
        [string]$Probe = "info"
    )

    # Native Docker errors are expected while Docker Desktop is starting.
    # Suppress them here so the launcher can print a clear, actionable status.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & docker $Probe *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Wait-ForDockerEngine {
    param(
        [int]$TimeoutSeconds = 120,
        [int]$PollIntervalSeconds = 5
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerEngine -Probe "info") {
            return $true
        }

        Write-Host "Waiting for Docker Desktop Engine..." -ForegroundColor Yellow
        Start-Sleep -Seconds $PollIntervalSeconds
    }

    return (Test-DockerEngine -Probe "info")
}

function Invoke-DockerCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "`n==> $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Wait-ForHealthyService {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int]$TimeoutSeconds = 90
    )

    Write-Host "`n==> Wait for $ServiceName health check" -ForegroundColor Cyan
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $containerId = docker compose ps -q $ServiceName 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($containerId)) {
            $status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $containerId 2>$null
            if ($LASTEXITCODE -eq 0 -and $status -eq "healthy") {
                return
            }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "$ServiceName did not become healthy within $TimeoutSeconds seconds (last status: $status)."
}

try {
    Write-Host "==> Check Docker Desktop" -ForegroundColor Cyan
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found. Install and start Docker Desktop, then try again."
    }

    if (-not (Test-DockerEngine -Probe "version")) {
        $dockerDesktopProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
        if (-not $dockerDesktopProcess) {
            $dockerDesktopCandidates = @(
                "C:\Program Files\Docker\Docker\Docker Desktop.exe",
                (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe")
            )
            $dockerDesktopPath = $dockerDesktopCandidates |
                Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
                Select-Object -First 1

            if ($dockerDesktopPath) {
                Write-Host "Docker Desktop is not running. Starting Docker Desktop..." -ForegroundColor Yellow
                Start-Process -FilePath $dockerDesktopPath
            }
            else {
                Write-Host "Docker Desktop executable was not found in a supported install location." -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "Docker Desktop is running; waiting for the Engine to become ready..." -ForegroundColor Yellow
        }

        if (-not (Wait-ForDockerEngine -TimeoutSeconds 120 -PollIntervalSeconds 5)) {
            throw @"
Docker Desktop is not running or Engine failed to start.
- Open Docker Desktop.
- Wait until Engine Running is shown.
- Run start_demo.bat again.
"@
        }
    }

    $dockerReady = $true
    docker version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Engine became unavailable during version verification."
    }

    if ($NoBuild) {
        Invoke-DockerCommand "Start Docker Compose services" { docker compose up -d }
    }
    else {
        Invoke-DockerCommand "Build and start Docker Compose services" { docker compose up --build -d }
    }

    Wait-ForHealthyService "backend"

    # This launcher is an explicit local environment initialization command. Compose
    # itself intentionally does not run migrations during container startup.
    Invoke-DockerCommand "Upgrade local database to Alembic head" {
        docker compose exec -T backend python -m alembic -c alembic.ini upgrade head
    }

    Invoke-DockerCommand "Verify Alembic revision" {
        docker compose exec -T backend python -m alembic -c alembic.ini current
    }

    $postgresUser = (docker compose exec -T postgres printenv POSTGRES_USER | Select-Object -Last 1).Trim()
    $postgresDatabase = (docker compose exec -T postgres printenv POSTGRES_DB | Select-Object -Last 1).Trim()
    if ([string]::IsNullOrWhiteSpace($postgresUser) -or [string]::IsNullOrWhiteSpace($postgresDatabase)) {
        throw "Unable to resolve the local database name or user."
    }

    $userCountOutput = docker compose exec -T postgres psql -U $postgresUser -d $postgresDatabase -Atc "SELECT count(*) FROM users;"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect local data."
    }
    $userCount = [int]($userCountOutput | Select-Object -Last 1)

    if ($userCount -eq 0 -and -not $NoSeed) {
        Invoke-DockerCommand "Seed local development data" {
            docker compose exec -T backend python backend/scripts/seed_demo.py
        }
    }
    elseif ($userCount -gt 0) {
        Write-Host "`n==> Local data already exists; seed skipped." -ForegroundColor DarkGreen
    }
    else {
        Write-Host "`n==> Empty database detected; seed skipped because -NoSeed was supplied." -ForegroundColor Yellow
    }

    Wait-ForHealthyService "frontend"

    $backend = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 15
    if ($backend.StatusCode -ne 200 -or $backend.Content -notmatch '"status"\s*:\s*"ok"') {
        throw "Backend health check returned an unexpected response."
    }

    $frontend = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 30
    if ($frontend.StatusCode -ne 200) {
        throw "Frontend returned HTTP $($frontend.StatusCode)."
    }

    Write-Host "`n==> CareerMatrix is ready" -ForegroundColor Green
    docker compose ps
    Write-Host "`nFrontend: http://localhost:3000"
    Write-Host "Backend:  http://localhost:8000"
    Write-Host "Health:   http://localhost:8000/health"

    if (-not $NoBrowser) {
        Write-Host "`n==> Open http://localhost:3000 in the default browser" -ForegroundColor Cyan
        Start-Process "http://localhost:3000"
    }
}
catch {
    Write-Host "`nCareerMatrix startup failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($dockerReady) {
        Write-Host "Run 'docker compose ps' and 'docker compose logs' for details." -ForegroundColor Yellow
    }
    exit 1
}
