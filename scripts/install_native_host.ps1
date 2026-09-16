param(
    [Parameter(Position = 0)]
    [string]$ExtensionId
)

$ErrorActionPreference = 'Stop'
$HostName = 'com.ai_job_copilot.service_control'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$NativeHostDirectory = Join-Path $ProjectRoot 'native_host'
$TemplatePath = Join-Path $NativeHostDirectory 'host_manifest.template.json'
$ManifestPath = Join-Path $NativeHostDirectory 'host_manifest.json'
$HostLauncher = Join-Path $NativeHostDirectory 'run_host.bat'
$RegistryPath = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"

if (-not [string]::IsNullOrWhiteSpace($env:AI_JOB_COPILOT_TEST_REGISTRY_PATH)) {
    $testRegistryPath = $env:AI_JOB_COPILOT_TEST_REGISTRY_PATH
    if ($testRegistryPath -cnotmatch '^HKCU:\\Software\\AIJobCopilot\\Tests\\[A-Za-z0-9._-]+(?:\\[A-Za-z0-9._-]+)*$') {
        throw 'The test Registry path must be inside HKCU:\Software\AIJobCopilot\Tests.'
    }
    $RegistryPath = $testRegistryPath
}

function ConvertTo-JsonStringContent {
    param([string]$Value)
    $json = ConvertTo-Json $Value -Compress
    return $json.Substring(1, $json.Length - 2)
}

function Get-ExtensionIdFromManifest {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        $existingManifest = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }
    if ($existingManifest.name -ne $HostName -or
        $existingManifest.type -ne 'stdio' -or
        $existingManifest.allowed_origins.Count -ne 1) {
        return $null
    }
    $origin = [string]$existingManifest.allowed_origins[0]
    if ($origin -cnotmatch '^chrome-extension://([a-p]{32})/$') {
        return $null
    }
    return $Matches[1]
}

if ([string]::IsNullOrWhiteSpace($ExtensionId)) {
    $ExtensionId = Get-ExtensionIdFromManifest -Path $ManifestPath
    if ([string]::IsNullOrWhiteSpace($ExtensionId)) {
        throw 'Extension ID is required. Copy it from edge://extensions and run install_native_host.bat <EDGE_EXTENSION_ID>.'
    }
    Write-Host 'Reusing the extension ID from the existing generated manifest.' -ForegroundColor Yellow
}

if ($ExtensionId -cnotmatch '^[a-p]{32}$') {
    throw 'Invalid extension ID. Copy the 32-character ID (a-p only) from edge://extensions.'
}
if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) {
    throw 'Native Host manifest template was not found.'
}
if (-not (Test-Path -LiteralPath $HostLauncher -PathType Leaf)) {
    throw 'The fixed Native Host launcher was not found.'
}

$resolvedManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
if (Test-Path -LiteralPath $RegistryPath) {
    $existingPath = (Get-Item -LiteralPath $RegistryPath).GetValue('')
    if (-not [string]::IsNullOrWhiteSpace($existingPath)) {
        try {
            $resolvedExistingPath = [System.IO.Path]::GetFullPath([string]$existingPath)
        }
        catch {
            throw 'The existing Native Host registration has an invalid path; refusing to overwrite it.'
        }
        if ($resolvedExistingPath -ne $resolvedManifestPath) {
            if (Test-Path -LiteralPath $resolvedExistingPath -PathType Leaf) {
                throw 'The Native Host name belongs to another active project directory; refusing to overwrite it.'
            }
            Write-Host 'Repairing a stale Native Host registration left by a moved project folder.' -ForegroundColor Yellow
        }
    }
}

$template = Get-Content -LiteralPath $TemplatePath -Raw -Encoding UTF8
$manifest = $template.Replace(
    '__HOST_PATH__',
    (ConvertTo-JsonStringContent ([System.IO.Path]::GetFullPath($HostLauncher)))
).Replace(
    '__ALLOWED_ORIGIN__',
    "chrome-extension://$ExtensionId/"
)

# Validate before writing or changing the registry.
$parsedManifest = $manifest | ConvertFrom-Json
if ($parsedManifest.name -ne $HostName -or
    $parsedManifest.type -ne 'stdio' -or
    $parsedManifest.allowed_origins.Count -ne 1 -or
    $parsedManifest.allowed_origins[0] -ne "chrome-extension://$ExtensionId/") {
    throw 'Generated Native Host manifest validation failed.'
}

[System.IO.File]::WriteAllText(
    $ManifestPath,
    $manifest,
    [System.Text.UTF8Encoding]::new($false)
)
New-Item -Path $RegistryPath -Force | Out-Null
Set-Item -LiteralPath $RegistryPath -Value $resolvedManifestPath

Write-Host 'Native Messaging Host installed for the current user.' -ForegroundColor Green
Write-Host "Allowed extension origin: chrome-extension://$ExtensionId/"
Write-Host 'Reload the extension at edge://extensions before use.'
