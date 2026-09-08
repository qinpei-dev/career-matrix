$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$launcherPath = Join-Path $projectRoot "start_demo.bat"
$desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)

try {
    if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        throw "CareerMatrix launcher was not found: $launcherPath"
    }
    if ([string]::IsNullOrWhiteSpace($desktopPath) -or -not (Test-Path -LiteralPath $desktopPath -PathType Container)) {
        throw "Windows Desktop directory could not be resolved."
    }

    $shortcutPath = Join-Path $desktopPath "CareerMatrix.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $launcherPath
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "Start the CareerMatrix local Docker environment"
    $shortcut.WindowStyle = 1

    $iconCandidates = @(
        (Join-Path $projectRoot "app.ico"),
        (Join-Path $projectRoot "assets\app.ico"),
        (Join-Path $projectRoot "frontend\public\favicon.ico")
    )
    $projectIcon = $iconCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ($projectIcon) {
        $shortcut.IconLocation = "$projectIcon,0"
    }

    $shortcut.Save()
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
        throw "Windows did not create the shortcut."
    }

    Write-Host "Desktop shortcut created:" -ForegroundColor Green
    Write-Host $shortcutPath
    Write-Host "Target: $launcherPath"
    Write-Host "Working directory: $projectRoot"
    if ($projectIcon) {
        Write-Host "Icon: $projectIcon"
    }
    else {
        Write-Host "Icon: Windows default (no project .ico file found)"
    }
}
catch {
    Write-Host "Unable to create desktop shortcut: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
