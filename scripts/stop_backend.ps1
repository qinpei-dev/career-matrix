$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Port = 8000

function Get-ProjectId {
    param([string]$Path)

    $normalizedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\').ToLowerInvariant()
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedPath)
        $hash = $sha256.ComputeHash($bytes)
        return (-join ($hash[0..7] | ForEach-Object { $_.ToString('x2') }))
    }
    finally {
        $sha256.Dispose()
    }
}

function Get-PidFilePath {
    $stateDirectory = Join-Path ([System.IO.Path]::GetTempPath()) 'AIJobCopilot'
    return Join-Path $stateDirectory ("backend-{0}.json" -f (Get-ProjectId $ProjectRoot))
}

function Get-ListeningProcessId {
    param([int]$LocalPort)

    try {
        $connection = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($null -ne $connection) {
            return [int]$connection.OwningProcess
        }
    }
    catch {
        # Fall back to netstat on Windows versions without Get-NetTCPConnection.
    }

    $lines = & netstat.exe -ano -p tcp 2>$null
    foreach ($line in $lines) {
        if ($line -match '^\s*TCP\s+\S+:8000\s+\S+\s+LISTENING\s+(\d+)\s*$') {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Get-ProcessDetails {
    param([int]$ProcessId)

    try {
        return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    }
    catch {
        try {
            $process = Get-Process -Id $ProcessId -ErrorAction Stop
            return [pscustomobject]@{
                ProcessId = $ProcessId
                Name = $process.ProcessName
                CommandLine = $null
            }
        }
        catch {
            return $null
        }
    }
}

function Test-IsJobCopilotBackend {
    param($ProcessDetails)

    if ($null -eq $ProcessDetails -or [string]::IsNullOrWhiteSpace($ProcessDetails.CommandLine)) {
        return $false
    }
    return ($ProcessDetails.CommandLine -match '(?i)uvicorn') -and
        ($ProcessDetails.CommandLine -match '(?i)backend\.app\.main:app')
}

function Test-ParentReferencesProject {
    param($ProcessDetails)

    if ($null -eq $ProcessDetails -or $null -eq $ProcessDetails.ParentProcessId) {
        return $false
    }
    $parentDetails = Get-ProcessDetails ([int]$ProcessDetails.ParentProcessId)
    if ($null -eq $parentDetails -or [string]::IsNullOrWhiteSpace($parentDetails.CommandLine)) {
        return $false
    }
    return $parentDetails.CommandLine -match [regex]::Escape($ProjectRoot)
}

function Remove-StateFile {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

try {
    Set-Location -LiteralPath $ProjectRoot
    $statePath = Get-PidFilePath
    $state = $null
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        }
        catch {
            Write-Host '警告：PID 记录无法读取，将仅做保守检查。' -ForegroundColor Yellow
        }
    }

    $listenerProcessId = Get-ListeningProcessId $Port
    if ($null -eq $listenerProcessId) {
        Write-Host "端口 $Port 当前没有监听进程；后端未运行。" -ForegroundColor Green
        Remove-StateFile $statePath
        exit 0
    }

    $details = Get-ProcessDetails $listenerProcessId
    $processName = if ($null -ne $details) { $details.Name } else { '未知' }
    $hasExpectedCommand = Test-IsJobCopilotBackend $details
    $stateMatches = ($null -ne $state) -and
        ($state.ProjectRoot -eq $ProjectRoot) -and
        ([int]$state.ListenerProcessId -eq $listenerProcessId)

    $hostMatches = ($null -ne $state) -and
        ($state.ProjectRoot -eq $ProjectRoot) -and
        ([int]$state.HostProcessId -gt 0) -and
        ([int]$details.ParentProcessId -eq [int]$state.HostProcessId)

    $parentMatches = Test-ParentReferencesProject $details

    if (-not $hasExpectedCommand -or (-not $stateMatches -and -not $hostMatches -and -not $parentMatches)) {
        Write-Host "无法确认 PID $listenerProcessId（进程 $processName）属于当前 CareerMatrix 后端。" -ForegroundColor Red
        if (-not $hasExpectedCommand) {
            Write-Host '命令行未同时包含 uvicorn 和 backend.app.main:app。'
        }
        if (-not $stateMatches -and -not $hostMatches -and -not $parentMatches) {
            Write-Host '当前项目的 PID 记录和父进程路径均无法证明进程归属。'
        }
        Write-Host '为避免误伤，脚本不会强制终止该进程。请人工确认并处理。'
        exit 1
    }

    Write-Host "正在停止 CareerMatrix 后端（PID $listenerProcessId，进程 $processName）..."
    Stop-Process -Id $listenerProcessId -ErrorAction Stop

    $deadline = (Get-Date).AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 250
        $remainingProcessId = Get-ListeningProcessId $Port
        if ($null -eq $remainingProcessId) {
            break
        }
    } while ((Get-Date) -lt $deadline)

    if ($null -ne (Get-ListeningProcessId $Port)) {
        Write-Host '后端未能在预期时间内停止。脚本不会强制结束其他进程，请人工检查。' -ForegroundColor Red
        exit 1
    }

    Remove-StateFile $statePath

    if ($null -ne $state -and [int]$state.HostProcessId -gt 0) {
        $hostProcessId = [int]$state.HostProcessId
        $hostDetails = Get-ProcessDetails $hostProcessId
        if ($null -ne $hostDetails -and
            ($hostMatches -or $hostDetails.CommandLine -match [regex]::Escape($ProjectRoot))) {
            Stop-Process -Id $hostProcessId -ErrorAction SilentlyContinue
        }
    }

    Write-Host 'CareerMatrix 后端已安全停止。' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "停止脚本发生错误：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host '未执行进一步的强制终止，请人工检查。'
    exit 1
}
