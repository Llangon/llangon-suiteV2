Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$PidPath = Join-Path $RuntimeRoot "web.pid"
$HostAddress = "127.0.0.1"
$Port = 8787
$EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"

if (Test-Path -LiteralPath $EnvPath) {
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        $Value = $Value.Trim().Trim('"').Trim("'")
        if ($Key -eq "INFONALIA_HOST" -and $Value) {
            $HostAddress = $Value
        }
        elseif ($Key -eq "INFONALIA_PORT" -and $Value) {
            $ParsedPort = 0
            if ([int]::TryParse($Value, [ref]$ParsedPort)) {
                $Port = $ParsedPort
            }
        }
    }
}

$HealthUrl = "http://127.0.0.1:$Port/api/health"

function Test-WebHealth {
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
        return @{
            Ok = ($Response.StatusCode -eq 200 -and $Response.Content -like '*"status": "ok"*')
            StatusCode = $Response.StatusCode
            Content = $Response.Content
            Error = ""
        }
    }
    catch {
        return @{
            Ok = $false
            StatusCode = ""
            Content = ""
            Error = $_.Exception.Message
        }
    }
}

function Get-WebListeners {
    try {
        return @(Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        return @()
    }
}

function Describe-Process {
    param([int]$ProcessId)
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return "PID $ProcessId (proceso no encontrado)"
    }
    return "PID $ProcessId ($($Process.ProcessName))"
}

Write-Host "Proyecto: $ProjectRoot"
Write-Host "Logs:     $LogDir"
Write-Host "URL:      $HealthUrl"
Write-Host ""

$TaskNames = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup"
)

foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        Write-Host "$TaskName : no instalada"
    }
    else {
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "$TaskName : $($Task.State) | ultima ejecucion: $($Info.LastRunTime) | resultado: $($Info.LastTaskResult)"
    }
}

Write-Host ""
$Listeners = @(Get-WebListeners)
if ($Listeners.Count -eq 0) {
    Write-Host "Puerto 127.0.0.1:$Port : sin LISTENING"
}
else {
    foreach ($Listener in $Listeners) {
        Write-Host "Puerto 127.0.0.1:$Port : LISTENING | $(Describe-Process -ProcessId $Listener.OwningProcess)"
    }
}

if (Test-Path -LiteralPath $PidPath) {
    $RecordedPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($RecordedPid) {
        Write-Host "PID registrado: $(Describe-Process -ProcessId ([int]$RecordedPid))"
    }
}
else {
    Write-Host "PID registrado: no existe runtime\\web.pid"
}

Write-Host ""
$Health = Test-WebHealth
if ($Health.Ok) {
    Write-Host "Healthcheck web: OK $($Health.StatusCode) $($Health.Content)"
}
elseif ($Listeners.Count -gt 0) {
    Write-Host "Healthcheck web: ERROR. Hay puerto LISTENING, pero /api/health no responde correctamente."
    if ($Health.Error) {
        Write-Host "Detalle: $($Health.Error)"
    }
}
else {
    $WebTask = Get-ScheduledTask -TaskName "LlangonSuite-Web" -ErrorAction SilentlyContinue
    if ($null -eq $WebTask) {
        Write-Host "Healthcheck web: ERROR. La tarea Web no esta instalada y no hay proceso escuchando."
    }
    elseif ($WebTask.State -eq "Running") {
        Write-Host "Healthcheck web: ERROR. La tarea Web aparece Running, pero no hay puerto LISTENING."
    }
    else {
        Write-Host "Healthcheck web: ERROR. Tarea instalada en estado $($WebTask.State), pero el proceso web no esta vivo."
    }
    if ($Health.Error) {
        Write-Host "Detalle: $($Health.Error)"
    }
}

Write-Host ""
foreach ($LogName in @("web.log", "web.stdout.log", "web.stderr.log", "scheduler.log", "backup.log")) {
    $LogPath = Join-Path $LogDir $LogName
    if (Test-Path -LiteralPath $LogPath) {
        $Item = Get-Item -LiteralPath $LogPath
        Write-Host "$LogName : $($Item.Length) bytes | $($Item.LastWriteTime)"
    }
    else {
        Write-Host "$LogName : no existe todavia"
    }
}

Write-Host ""
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}
try {
    Push-Location -LiteralPath $ProjectRoot
    Write-Host "Estado trabajos scheduler:"
    & $Python -m webapp.infonalia_webapp.monitor.scheduler --status
}
catch {
    Write-Host "Estado trabajos scheduler: no disponible ($($_.Exception.Message))"
}
finally {
    Pop-Location
}

Write-Host ""
$Cloudflared = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
if ($null -eq $Cloudflared) {
    Write-Host "Cloudflare Tunnel: no instalado como servicio en este equipo."
}
else {
    Write-Host "Cloudflare Tunnel: $($Cloudflared.Status)"
}
