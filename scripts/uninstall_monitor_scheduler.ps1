param(
  [string]$TaskName = "LlangonSuiteV2-MonitorScheduler"
)

$ErrorActionPreference = "Stop"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Tarea eliminada: $TaskName"
} else {
  Write-Host "La tarea no existe: $TaskName"
}
