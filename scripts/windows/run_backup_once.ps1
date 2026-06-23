Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$LogPath = Join-Path $LogDir "backup.log"
Set-Location -LiteralPath $ProjectRoot

"[$(Get-Date -Format s)] Ejecutando copia SQLite..." | Out-File -FilePath $LogPath -Append -Encoding utf8
& $Python -m webapp.infonalia_webapp.backup_sqlite 2>&1 | Tee-Object -FilePath $LogPath -Append
exit $LASTEXITCODE

