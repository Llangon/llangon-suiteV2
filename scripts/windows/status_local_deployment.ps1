Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
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

function Get-EnvValue {
    param([string]$Name, [string]$Default = "")
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($Value) {
        return $Value
    }
    if (Test-Path -LiteralPath $EnvPath) {
        foreach ($Line in Get-Content -LiteralPath $EnvPath) {
            $Trimmed = $Line.Trim()
            if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
                continue
            }
            $Key, $RawValue = $Trimmed.Split("=", 2)
            if ($Key.Trim() -eq $Name) {
                return $RawValue.Trim().Trim('"').Trim("'")
            }
        }
    }
    return $Default
}

function Get-TaskWakeEnabled {
    param([string]$TaskName)
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        return "no disponible"
    }
    return $Task.Settings.WakeToRun
}

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
        return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
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

function Format-TaskScheduleSummary {
    param([Microsoft.Management.Infrastructure.CimInstance[]]$Triggers)
    if ($null -eq $Triggers -or $Triggers.Count -eq 0) {
        return "sin triggers"
    }

    $Parts = @()
    foreach ($Trigger in $Triggers) {
        $TypeName = ""
        if ($Trigger.PSObject.Properties.Match("CimClass").Count -gt 0) {
            $TypeName = $Trigger.CimClass.CimClassName
        }

        $Summary = ""
        if ($Trigger.StartBoundary) {
            try {
                $Start = [datetime]$Trigger.StartBoundary
                $Summary = $Start.ToString("HH:mm")
            }
            catch {
                $Summary = "$($Trigger.StartBoundary)"
            }
        }

        if ($Summary) {
            if ($TypeName) {
                $Parts += "${TypeName}: ${Summary}"
            }
            else {
                $Parts += $Summary
            }
        }
    }

    if ($Parts.Count -eq 0) {
        return "sin configuracion horaria detectada"
    }

    return ($Parts -join " | ")
}

Write-Host "Proyecto: $ProjectRoot"
Write-Host "Logs:     $LogDir"
Write-Host "URL:      $HealthUrl"
Write-Host ""

$TaskNames = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake"
)

foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        Write-Host "$TaskName : no instalada"
    }
    else {
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        $ScheduleSummary = Format-TaskScheduleSummary -Triggers $Task.Triggers
        Write-Host "$TaskName : $($Task.State) | ultima ejecucion: $($Info.LastRunTime) | resultado: $($Info.LastTaskResult)"
        Write-Host "  - Trigger: $ScheduleSummary"
        if ($Info.NextRunTime) {
            Write-Host "  - Siguiente ejecucion: $($Info.NextRunTime)"
        }
    }
}

Write-Host ""
$AgendaWakeLog = Join-Path $LogDir "agenda_wake.log"
Write-Host "AgendaWake:"
Write-Host "  Tarea instalada: $([bool](Get-ScheduledTask -TaskName 'LlangonSuite-AgendaWake' -ErrorAction SilentlyContinue))"
Write-Host "  Wake enabled: $(Get-TaskWakeEnabled -TaskName 'LlangonSuite-AgendaWake')"
Write-Host "  Habilitada por config: $(Get-EnvValue -Name 'LLANGON_AGENDA_WAKE_ENABLED' -Default '0')"
Write-Host "  Hora configurada: $(Get-EnvValue -Name 'LLANGON_AGENDA_WAKE_TIME' -Default '06:00')"
Write-Host "  Laborables solamente: $(Get-EnvValue -Name 'MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY' -Default '1')"
Write-Host "  Auto suspension: $(Get-EnvValue -Name 'LLANGON_AGENDA_WAKE_AUTO_SLEEP' -Default '1')"
Write-Host "  Omitir si usuario activo: $(Get-EnvValue -Name 'LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE' -Default '1')"
Write-Host "  Log: $AgendaWakeLog"

Write-Host ""
$FullBackupEnabled = Get-EnvValue -Name "LLANGON_FULL_BACKUP_ENABLED" -Default "0"
$FullBackupRoot = Get-EnvValue -Name "LLANGON_FULL_BACKUP_ROOT" -Default ""
$SqliteBackupDir = Get-EnvValue -Name "LLANGON_SQLITE_BACKUP_DIR" -Default (Join-Path $RuntimeRoot "backups\sqlite")
Write-Host "Backups:"
Write-Host "  SQLite local: $SqliteBackupDir"
Write-Host "  Backup completo privado activado: $FullBackupEnabled"
if ($FullBackupRoot) {
    Write-Host "  Ruta backup completo: $FullBackupRoot"
    if (Test-Path -LiteralPath $FullBackupRoot) {
        $LatestFullBackup = Get-ChildItem -LiteralPath $FullBackupRoot -Recurse -Filter "*_LLANGON_SUITE_FULL_PRIVATE_BACKUP.zip" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($LatestFullBackup) {
            $LatestManifest = $LatestFullBackup.FullName -replace "\.zip$", "_manifest.json"
            Write-Host "  Ultimo backup completo: $($LatestFullBackup.FullName)"
            Write-Host "  Fecha: $($LatestFullBackup.LastWriteTime)"
            Write-Host "  Tamano: $($LatestFullBackup.Length) bytes"
            if (Test-Path -LiteralPath $LatestManifest) {
                Write-Host "  Manifest: $LatestManifest"
                try {
                    $ManifestJson = Get-Content -Raw -LiteralPath $LatestManifest | ConvertFrom-Json
                    if ($ManifestJson.status) {
                        Write-Host "  Estado manifest: $($ManifestJson.status)"
                    }
                    if ($ManifestJson.errors -and $ManifestJson.errors.Count -gt 0) {
                        Write-Host "  Ultimo error: $($ManifestJson.errors -join '; ')"
                    }
                }
                catch {
                    Write-Host "  Manifest: no se pudo leer ($($_.Exception.Message))"
                }
            }
            else {
                Write-Host "  Manifest: no localizado junto al ZIP"
            }
        }
        else {
            Write-Host "  Ultimo backup completo: no localizado"
        }
    }
    else {
        Write-Host "  Ruta backup completo: no existe todavia"
    }
}
else {
    Write-Host "  Ruta backup completo: no configurada"
}

Write-Host ""
$Listeners = @(Get-WebListeners)
if ($Listeners.Count -eq 0) {
    if ((Test-WebHealth).Ok) {
        Write-Host "Puerto ${HostAddress}:$Port : healthcheck OK; LISTENING no visible por Get-NetTCPConnection"
    }
    else {
        Write-Host "Puerto ${HostAddress}:$Port : sin LISTENING"
    }
}
else {
    foreach ($Listener in $Listeners) {
        Write-Host "Puerto $($Listener.LocalAddress):$Port : LISTENING | $(Describe-Process -ProcessId $Listener.OwningProcess)"
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
foreach ($LogName in @("web.log", "web.stdout.log", "web.stderr.log", "scheduler.log", "backup.log", "full_backup.log")) {
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
