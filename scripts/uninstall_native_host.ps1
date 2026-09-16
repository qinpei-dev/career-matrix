$ErrorActionPreference = 'Stop'
$HostName = 'com.ai_job_copilot.service_control'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $ProjectRoot 'native_host\host_manifest.json'
$RegistryPath = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"

if (-not [string]::IsNullOrWhiteSpace($env:AI_JOB_COPILOT_TEST_REGISTRY_PATH)) {
    $testRegistryPath = $env:AI_JOB_COPILOT_TEST_REGISTRY_PATH
    if ($testRegistryPath -cnotmatch '^HKCU:\\Software\\AIJobCopilot\\Tests\\[A-Za-z0-9._-]+(?:\\[A-Za-z0-9._-]+)*$') {
        throw 'The test Registry path must be inside HKCU:\Software\AIJobCopilot\Tests.'
    }
    $RegistryPath = $testRegistryPath
}

$resolvedManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)

if (-not (Test-Path -LiteralPath $RegistryPath)) {
    Write-Host 'The Native Messaging Host is not installed for this project.' -ForegroundColor Yellow
    exit 0
}

$registeredPath = (Get-Item -LiteralPath $RegistryPath).GetValue('')
try {
    $resolvedRegisteredPath = [System.IO.Path]::GetFullPath([string]$registeredPath)
}
catch {
    throw 'The registration path is invalid; refusing to remove another Host.'
}

if ($resolvedRegisteredPath -ne $resolvedManifestPath) {
    if (Test-Path -LiteralPath $resolvedRegisteredPath -PathType Leaf) {
        throw 'The Native Host points to another active project directory; refusing to remove it.'
    }
    Write-Host 'Removing a stale Native Host registration left by a moved project folder.' -ForegroundColor Yellow
}

Remove-Item -LiteralPath $RegistryPath -Force
if (Test-Path -LiteralPath $ManifestPath -PathType Leaf) {
    Remove-Item -LiteralPath $ManifestPath -Force
}

Write-Host 'The Native Messaging Host for this project was uninstalled.' -ForegroundColor Green
Write-Host 'The extension, project, .env, and running backend were not changed.'
