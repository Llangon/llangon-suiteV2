param(
  [string]$TaskName = "LlangonSuiteV2-MonitorScheduler",
  [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Runner = Join-Path $ProjectRoot "scripts\run_monitor_scheduler_once.ps1"
$HiddenRunner = Join-Path $ProjectRoot "scripts\run_monitor_scheduler_hidden.vbs"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "monitor_scheduler.log"

if (!(Test-Path -LiteralPath $Python)) {
  throw "No se encuentra Python en $Python"
}
if (!(Test-Path -LiteralPath $Runner)) {
  throw "No se encuentra el runner en $Runner"
}
if (!(Test-Path -LiteralPath $HiddenRunner)) {
  throw "No se encuentra el runner oculto en $HiddenRunner"
}
if (!(Test-Path -LiteralPath $LogDir)) {
  New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$ActionArgs = "`"$HiddenRunner`" `"$ProjectRoot`""
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument $ActionArgs -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
if ($RunAsSystem) {
  $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
} else {
  $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Tarea instalada o actualizada: $TaskName"
Write-Host "Proyecto: $ProjectRoot"
Write-Host "Runner: $Runner"
Write-Host "Runner oculto: $HiddenRunner"
Write-Host "Log: $LogFile"
if ($RunAsSystem) {
  Write-Host "Cuenta: SYSTEM (funciona sin sesion de usuario abierta)"
} else {
  Write-Host "Cuenta: usuario actual interactivo"
  Write-Host "Para funcionar sin sesion de usuario abierta, ejecuta este script como administrador con -RunAsSystem."
}
