Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Names = @(
    "LlangonSuite-KeeperTick",
    "LlangonSuite-WakeTick",
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake",
    "LlangonSuiteV2-MonitorScheduler"
)
$Legacy = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup",
    "LlangonSuite-AgendaWake",
    "LlangonSuiteV2-MonitorScheduler"
)

function Get-ObjectProperty {
    param(
        [object]$Object,
        [string]$Name
    )
    if ($null -eq $Object) {
        return $null
    }
    $Property = $Object.PSObject.Properties[$Name]
    if ($null -eq $Property) {
        return $null
    }
    return $Property.Value
}

Write-Host "Estado limpio de automatizaciones Llangon Suite"
Write-Host ""
foreach ($Name in $Names) {
    $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        Write-Host "$Name : no existe"
        continue
    }
    $Info = Get-ScheduledTaskInfo -TaskName $Name
    $Actions = ($Task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " || "
    $Triggers = ($Task.Triggers | ForEach-Object {
        $Repetition = Get-ObjectProperty $_ "Repetition"
        "Type=$($_.CimClass.CimClassName); Start=$(Get-ObjectProperty $_ "StartBoundary"); DaysOfWeek=$(Get-ObjectProperty $_ "DaysOfWeek"); Interval=$(Get-ObjectProperty $Repetition "Interval")"
    }) -join " || "
    $Marker = if ($Legacy -contains $Name) { "  [LEGACY: revisar/eliminar]" } else { "" }
    Write-Host "$Name$Marker"
    Write-Host "  Estado: $($Task.State) | Habilitada: $($Task.Settings.Enabled) | WakeToRun: $($Task.Settings.WakeToRun)"
    Write-Host "  Ultima: $($Info.LastRunTime) | Proxima: $($Info.NextRunTime) | Resultado: $($Info.LastTaskResult)"
    Write-Host "  Triggers: $Triggers"
    Write-Host "  Accion: $Actions"
}
