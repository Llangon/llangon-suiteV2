Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

foreach ($Name in @("LlangonSuite-KeeperTick", "LlangonSuite-WakeTick")) {
    $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($Task) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Host "Eliminada: $Name"
    }
    else {
        Write-Host "No existe: $Name"
    }
}
