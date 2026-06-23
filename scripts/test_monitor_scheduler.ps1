param(
  [switch]$DryRun,
  [switch]$ListSchedule,
  [switch]$ResetTestState,
  [string[]]$ScheduleKey = @(),
  [string]$Now = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $Python)) {
  throw "No se encuentra Python en $Python"
}

$ArgsList = @("-m", "webapp.infonalia_webapp.monitor.scheduler")
if ($ListSchedule) {
  $ArgsList += "--list-schedule"
} elseif ($ResetTestState) {
  $ArgsList += "--reset-test-state"
  foreach ($Key in $ScheduleKey) {
    $ArgsList += @("--schedule-key", $Key)
  }
} elseif ($DryRun) {
  $ArgsList += "--dry-run"
} else {
  $ArgsList += "--once"
}
if ($Now) {
  $ArgsList += @("--now", $Now)
}

Push-Location $ProjectRoot
try {
  & $Python @ArgsList
} finally {
  Pop-Location
}
