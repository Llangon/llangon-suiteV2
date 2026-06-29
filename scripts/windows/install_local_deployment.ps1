Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "logs"), (Join-Path $RuntimeRoot "locks") | Out-Null

$ScriptHostExe = (Get-Command wscript.exe).Source
$HiddenRunner = Join-Path $ScriptRoot "run_powershell_hidden.vbs"
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
        [TimeSpan]$ExecutionTimeLimit
    )

    $Arguments = "`"$HiddenRunner`" `"$ScriptPath`""
    $Action = New-ScheduledTaskAction -Execute $ScriptHostExe -Argument $Arguments -WorkingDirectory $ProjectRoot
    $Settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit $ExecutionTimeLimit

    Register-ScheduledTask `
        -TaskName $Name `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description $Description `
        -Force | Out-Null
}

$WebScript = Join-Path $ScriptRoot "start_web_production.ps1"
$SchedulerScript = Join-Path $ScriptRoot "run_scheduler_once.ps1"
$BackupScript = Join-Path $ScriptRoot "run_backup_once.ps1"

$WebTrigger = New-ScheduledTaskTrigger -AtLogOn
$SchedulerTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At ((Get-Date).Date.AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Minutes $SchedulerMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$BackupTrigger = New-ScheduledTaskTrigger -Daily -At 03:30

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

Write-Host "Tareas instaladas o actualizadas:"
Write-Host " - LlangonSuite-Web"
Write-Host " - LlangonSuite-Scheduler"
Write-Host " - LlangonSuite-Backup"
