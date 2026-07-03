Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TaskNames = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake"
)

foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $Task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Tarea eliminada: $TaskName"
    }
    else {
        Write-Host "No existia la tarea: $TaskName"
    }
}

Write-Host "No se han borrado datos, logs ni copias de seguridad."
