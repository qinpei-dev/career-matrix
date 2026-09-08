param(
    [switch]$Hidden
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendEntry = Join-Path $ProjectRoot 'backend\app\main.py'
$EnvFile = Join-Path $ProjectRoot '.env'
$HealthUrl = 'http://127.0.0.1:8000/health'
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
    if (-not (Test-Path -LiteralPath $stateDirectory)) {
        New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
    }
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

function Get-BackendState {
    $statePath = Get-PidFilePath
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Test-IsCurrentProjectBackend {
    param(
        $ProcessDetails,
        [int]$ListenerProcessId
    )

    if (-not (Test-IsJobCopilotBackend $ProcessDetails)) {
        return $false
    }

    $state = Get-BackendState
    $stateMatches = ($null -ne $state) -and
        ($state.ProjectRoot -eq $ProjectRoot) -and
        ([int]$state.ListenerProcessId -eq $ListenerProcessId)
    $hostMatches = ($null -ne $state) -and
        ($state.ProjectRoot -eq $ProjectRoot) -and
        ([int]$state.HostProcessId -gt 0) -and
        ([int]$ProcessDetails.ParentProcessId -eq [int]$state.HostProcessId)
    return $stateMatches -or $hostMatches -or (Test-ParentReferencesProject $ProcessDetails)
}

function Get-HealthResult {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        $body = $response.Content | ConvertFrom-Json
        if ($response.StatusCode -eq 200 -and $body.status -eq 'ok') {
            return [pscustomobject]@{ Healthy = $true; Message = 'HTTP 200, status=ok' }
        }
        return [pscustomobject]@{
            Healthy = $false
            Message = "HTTP $($response.StatusCode)，响应不符合预期"
        }
    }
    catch {
        return [pscustomobject]@{ Healthy = $false; Message = $_.Exception.Message }
    }
}

function Save-BackendState {
    param(
        [int]$HostProcessId,
        [Nullable[int]]$ListenerProcessId
    )

    $state = [ordered]@{
        ProjectRoot = $ProjectRoot
        HostProcessId = $HostProcessId
        ListenerProcessId = $ListenerProcessId
        StartedAt = (Get-Date).ToString('o')
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath (Get-PidFilePath) -Encoding UTF8
}

try {
    Set-Location -LiteralPath $ProjectRoot

    $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $pythonCommand) {
        Write-Host '错误：未找到 Python。请先安装 Python，并确保 python 命令可用。' -ForegroundColor Red
        exit 1
    }

    & $pythonCommand.Source --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '错误：Python 命令无法正常运行。请检查 Python 安装和 PATH。' -ForegroundColor Red
        exit 1
    }

    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        Write-Host "错误：项目根目录缺少 .env 文件：$EnvFile" -ForegroundColor Red
        Write-Host '脚本不会创建或修改 .env。请按项目说明完成配置。'
        exit 1
    }

    if (-not (Test-Path -LiteralPath $BackendEntry -PathType Leaf)) {
        Write-Host "错误：找不到后端入口文件：$BackendEntry" -ForegroundColor Red
        exit 1
    }

    $existingProcessId = Get-ListeningProcessId $Port
    if ($null -ne $existingProcessId) {
        $details = Get-ProcessDetails $existingProcessId
        $processName = if ($null -ne $details) { $details.Name } else { '未知' }

        if (Test-IsCurrentProjectBackend -ProcessDetails $details -ListenerProcessId $existingProcessId) {
            Write-Host "后端已经运行（PID $existingProcessId，进程 $processName）。" -ForegroundColor Yellow
            $health = Get-HealthResult
            Write-Host "健康检查：$($health.Message)" -ForegroundColor $(if ($health.Healthy) { 'Green' } else { 'Yellow' })
            $state = Get-BackendState
            $hostProcessId = if (($null -ne $state) -and
                ($state.ProjectRoot -eq $ProjectRoot) -and
                ([int]$state.HostProcessId -gt 0)) {
                [int]$state.HostProcessId
            }
            else {
                0
            }
            Save-BackendState -HostProcessId $hostProcessId -ListenerProcessId $existingProcessId
            exit 0
        }

        Write-Host "端口冲突：127.0.0.1:$Port 已被其他程序占用。" -ForegroundColor Red
        Write-Host "可安全获取的信息：PID $existingProcessId，进程 $processName。"
        Write-Host '为避免误伤，脚本不会结束该进程。请人工确认并处理端口冲突。'
        exit 1
    }

    Write-Host '正在启动 CareerMatrix 后端...'
    Write-Host '将打开一个后端日志窗口；此窗口必须保持打开。' -ForegroundColor Yellow
    Write-Host '关闭该窗口后，AI 分析会停止。' -ForegroundColor Yellow

    $escapedRoot = $ProjectRoot.Replace("'", "''")
    $escapedPython = $pythonCommand.Source.Replace("'", "''")
    $childCommand = @"
`$Host.UI.RawUI.WindowTitle = 'CareerMatrix Backend'
Set-Location -LiteralPath '$escapedRoot'
Write-Host 'CareerMatrix 后端日志窗口。此窗口必须保持打开；关闭后 AI 分析会停止。' -ForegroundColor Yellow
& '$escapedPython' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
`$backendExitCode = `$LASTEXITCODE
Write-Host "后端进程已退出，退出码：`$backendExitCode" -ForegroundColor Yellow
"@
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childCommand))
    $backendArguments = @('-NoLogo', '-NoProfile')
    if (-not $Hidden) {
        $backendArguments += '-NoExit'
    }
    $backendArguments += @('-EncodedCommand', $encodedCommand)
    $backendWindowStyle = if ($Hidden) { 'Hidden' } else { 'Normal' }
    $backendWindow = Start-Process -FilePath 'powershell.exe' `
        -ArgumentList $backendArguments `
        -WindowStyle $backendWindowStyle `
        -PassThru

    Write-Host "后端日志窗口 PID：$($backendWindow.Id)"
    Save-BackendState -HostProcessId $backendWindow.Id -ListenerProcessId $null

    $deadline = (Get-Date).AddSeconds(10)
    $lastHealth = $null
    $listenerProcessId = $null
    do {
        Start-Sleep -Milliseconds 750
        $listenerProcessId = Get-ListeningProcessId $Port
        if ($null -ne $listenerProcessId) {
            $listenerDetails = Get-ProcessDetails $listenerProcessId
            if (-not (Test-IsCurrentProjectBackend -ProcessDetails $listenerDetails -ListenerProcessId $listenerProcessId)) {
                Write-Host "端口 $Port 在启动过程中被其他程序占用（PID $listenerProcessId）。" -ForegroundColor Red
                Write-Host '脚本不会结束该进程。请查看后端日志窗口。'
                exit 1
            }
            Save-BackendState -HostProcessId $backendWindow.Id -ListenerProcessId $listenerProcessId
            $lastHealth = Get-HealthResult
            if ($lastHealth.Healthy) {
                Write-Host "监听进程 PID：$listenerProcessId"
                Write-Host '后端启动成功，可以在 Edge 扩展中分析岗位。' -ForegroundColor Green
                exit 0
            }
        }
    } while ((Get-Date) -lt $deadline)

    if ($null -ne $lastHealth) {
        Write-Host "最后一次健康检查：$($lastHealth.Message)" -ForegroundColor Yellow
    }
    Write-Host '后端未能在预期时间内通过健康检查，请查看当前窗口日志。' -ForegroundColor Red
    exit 1
}
catch {
    Write-Host "启动脚本发生错误：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
