Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "logs"), (Join-Path $RuntimeRoot "locks") | Out-Null

$ScriptHostExe = (Get-Command wscript.exe).Source
$HiddenRunner = Join-Path $ScriptRoot "run_powershell_hidden.vbs"

function Import-LlangonEnvFile {
    $EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        $Key = $Key.Trim()
        if (-not $Key -or [Environment]::GetEnvironmentVariable($Key, "Process")) {
            continue
        }
        [Environment]::SetEnvironmentVariable($Key, $Value.Trim().Trim('"').Trim("'"), "Process")
    }
}

function Get-EnvBool {
    param([string]$Name, [bool]$Default)
    $Raw = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($null -eq $Raw -or $Raw.Trim() -eq "") {
        return $Default
    }
    return @("1", "true", "yes", "on", "si", "sí") -contains $Raw.Trim().ToLowerInvariant()
}

function Get-EnvTime {
    param([string]$Name, [string]$Default)
    $Raw = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($null -eq $Raw -or $Raw.Trim() -eq "") {
        $Raw = $Default
    }
    $Parsed = [datetime]::MinValue
    if (-not [datetime]::TryParseExact($Raw.Trim(), "HH:mm", [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$Parsed)) {
        $Parsed = [datetime]::ParseExact($Default, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
    }
    return (Get-Date).Date.AddHours($Parsed.Hour).AddMinutes($Parsed.Minute)
}

Import-LlangonEnvFile

$SchedulerMinutes = 5
if ($env:MONITOR_SCHEDULER_POLL_MINUTES) {
    $Parsed = 0
    if ([int]::TryParse($env:MONITOR_SCHEDULER_POLL_MINUTES, [ref]$Parsed) -and $Parsed -gt 0) {
        $SchedulerMinutes = $Parsed
    }
}

function Register-LlangonTask {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [Microsoft.Management.Infrastructure.CimInstance[]]$Trigger,
        [string]$Description,
        [TimeSpan]$ExecutionTimeLimit,
        [bool]$WakeToRun = $false,
        [bool]$Enabled = $true
    )

    $Arguments = "`"$HiddenRunner`" `"$ScriptPath`""
    $Action = New-ScheduledTaskAction -Execute $ScriptHostExe -Argument $Arguments -WorkingDirectory $ProjectRoot
    $Settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -WakeToRun:$WakeToRun `
        -ExecutionTimeLimit $ExecutionTimeLimit

    Register-ScheduledTask `
        -TaskName $Name `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description $Description `
        -Force | Out-Null

    if ($Enabled) {
        Enable-ScheduledTask -TaskName $Name | Out-Null
    }
    else {
        Disable-ScheduledTask -TaskName $Name | Out-Null
    }
}

$WebScript = Join-Path $ScriptRoot "start_web_production.ps1"
$SchedulerScript = Join-Path $ScriptRoot "run_scheduler_once.ps1"
$BackupScript = Join-Path $ScriptRoot "run_backup_once.ps1"
$AgendaWakeScript = Join-Path $ScriptRoot "run_agenda_wake_once.ps1"
$AgendaWakeEnabled = Get-EnvBool "LLANGON_AGENDA_WAKE_ENABLED" $false
$AgendaWakeAt = Get-EnvTime "LLANGON_AGENDA_WAKE_TIME" "06:00"
$AgendaWakeWeekdaysOnly = Get-EnvBool "MONITOR_AGENDA_PENDING_DAILY_WEEKDAYS_ONLY" $true

$WebTrigger = New-ScheduledTaskTrigger -AtLogOn
$SchedulerTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At ((Get-Date).Date.AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Minutes $SchedulerMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$BackupTrigger = New-ScheduledTaskTrigger -Daily -At 03:30
if ($AgendaWakeWeekdaysOnly) {
    $AgendaWakeTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $AgendaWakeAt
}
else {
    $AgendaWakeTrigger = New-ScheduledTaskTrigger -Daily -At $AgendaWakeAt
}

Register-LlangonTask `
    -Name "LlangonSuite-Web" `
    -ScriptPath $WebScript `
    -Trigger $WebTrigger `
    -Description "Servidor local de Llangon Suite en 127.0.0.1:8787." `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-LlangonTask `
    -Name "LlangonSuite-Scheduler" `
    -ScriptPath $SchedulerScript `
    -Trigger $SchedulerTrigger `
    -Description "Ejecucion periodica del scheduler de Llangon Suite." `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-LlangonTask `
    -Name "LlangonSuite-Backup" `
    -ScriptPath $BackupScript `
    -Trigger $BackupTrigger `
    -Description "Copia diaria de la base SQLite de Llangon Suite." `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-LlangonTask `
    -Name "LlangonSuite-AgendaWake" `
    -ScriptPath $AgendaWakeScript `
    -Trigger $AgendaWakeTrigger `
    -Description "Despierta el equipo para ejecutar agenda_pendientes_diaria y suspende si es seguro." `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -WakeToRun $true `
    -Enabled $AgendaWakeEnabled

Write-Host "Tareas instaladas o actualizadas:"
Write-Host " - LlangonSuite-Web"
Write-Host " - LlangonSuite-Scheduler"
Write-Host " - LlangonSuite-Backup"
if ($AgendaWakeEnabled) {
    Write-Host " - LlangonSuite-AgendaWake (activa, wake enabled)"
}
else {
    Write-Host " - LlangonSuite-AgendaWake (instalada desactivada; activar con LLANGON_AGENDA_WAKE_ENABLED=1)"
}
