Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$LockDir = Join-Path $RuntimeRoot "locks"
New-Item -ItemType Directory -Force -Path $LogDir, $LockDir | Out-Null

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$LogPath = Join-Path $LogDir "scheduler.log"
$LockPath = Join-Path $LockDir "scheduler.lock"
$StaleMinutes = 120

if (Test-Path -LiteralPath $LockPath) {
    $LockAge = (Get-Date) - (Get-Item -LiteralPath $LockPath).LastWriteTime
    if ($LockAge.TotalMinutes -lt $StaleMinutes) {
        "[$(Get-Date -Format s)] Scheduler omitido: ejecucion anterior todavia activa." | Out-File -FilePath $LogPath -Append -Encoding utf8
        exit 0
    }
    Remove-Item -LiteralPath $LockPath -Force
}

New-Item -ItemType File -Path $LockPath -Force | Out-Null
try {
    Set-Location -LiteralPath $ProjectRoot
    "[$(Get-Date -Format s)] Ejecutando scheduler una vez..." | Out-File -FilePath $LogPath -Append -Encoding utf8
    & $Python -m webapp.infonalia_webapp.monitor.scheduler --once 2>&1 | ForEach-Object {
        $_ | Out-File -FilePath $LogPath -Append -Encoding utf8
    }
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) {
        $ExitCode = 0
    }
    exit $ExitCode
}
finally {
    if (Test-Path -LiteralPath $LockPath) {
        Remove-Item -LiteralPath $LockPath -Force
    }
}
