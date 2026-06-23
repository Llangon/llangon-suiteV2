param(
  [string]$ProjectRoot = "",
  [int]$MaxLogBytes = 5242880,
  [int]$KeepLogFiles = 5
)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) {
  $ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
} else {
  $ProjectRoot = Resolve-Path $ProjectRoot
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "monitor_scheduler.log"

if (!(Test-Path -LiteralPath $Python)) {
  throw "No se encuentra Python en $Python"
}
if (!(Test-Path -LiteralPath $LogDir)) {
  New-Item -ItemType Directory -Path $LogDir | Out-Null
}

if ((Test-Path -LiteralPath $LogFile) -and ((Get-Item -LiteralPath $LogFile).Length -ge $MaxLogBytes)) {
  for ($i = $KeepLogFiles; $i -ge 1; $i--) {
    $Older = "$LogFile.$i"
    $Newer = "$LogFile." + ($i + 1)
    if (Test-Path -LiteralPath $Older) {
      if ($i -eq $KeepLogFiles) {
        Remove-Item -LiteralPath $Older -Force
      } else {
        Move-Item -LiteralPath $Older -Destination $Newer -Force
      }
    }
  }
  Move-Item -LiteralPath $LogFile -Destination "$LogFile.1" -Force
}

$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$Stamp] monitor scheduler --once" | Out-File -LiteralPath $LogFile -Append -Encoding utf8

Push-Location $ProjectRoot
try {
  $Output = & $Python -m webapp.infonalia_webapp.monitor.scheduler --once *>&1
  $ExitCode = $LASTEXITCODE
  $Output | Out-File -LiteralPath $LogFile -Append -Encoding utf8
  $Output
  exit $ExitCode
} finally {
  Pop-Location
}
