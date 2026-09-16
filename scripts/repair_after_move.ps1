$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$shortcutScript = Join-Path $PSScriptRoot 'create_desktop_shortcut.ps1'
$nativeHostInstaller = Join-Path $PSScriptRoot 'install_native_host.ps1'
$manifestPath = Join-Path $projectRoot 'native_host\host_manifest.json'

try {
    & $shortcutScript
    if (-not $?) {
        throw 'Desktop shortcut repair failed.'
    }

    if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
        & $nativeHostInstaller
    }
    else {
        Write-Host 'No generated Native Host manifest was found; the desktop shortcut was repaired.' -ForegroundColor Yellow
        Write-Host 'If you use the Edge extension, run install_native_host.bat <EDGE_EXTENSION_ID> once.' -ForegroundColor Yellow
    }

    Write-Host 'Folder move repair completed.' -ForegroundColor Green
}
catch {
    Write-Host "Unable to repair the moved installation: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
