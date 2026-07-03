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
& $Python -m webapp.infonalia_webapp.backup_sqlite 2>&1 | ForEach-Object {
    $_ | Out-File -FilePath $LogPath -Append -Encoding utf8
}
$ExitCode = $LASTEXITCODE
if ($null -eq $ExitCode) {
    $ExitCode = 0
}
if ($ExitCode -ne 0) {
    "[$(Get-Date -Format s)] Copia SQLite fallida. No se ejecuta backup completo." | Out-File -FilePath $LogPath -Append -Encoding utf8
    exit $ExitCode
}

"[$(Get-Date -Format s)] Ejecutando backup completo privado si esta activado..." | Out-File -FilePath $LogPath -Append -Encoding utf8
& $Python -m webapp.infonalia_webapp.full_backup --once 2>&1 | ForEach-Object {
    $_ | Out-File -FilePath $LogPath -Append -Encoding utf8
}
$FullBackupExitCode = $LASTEXITCODE
if ($null -eq $FullBackupExitCode) {
    $FullBackupExitCode = 0
}
if ($FullBackupExitCode -ne 0) {
    "[$(Get-Date -Format s)] Backup completo fallido. Codigo: $FullBackupExitCode" | Out-File -FilePath $LogPath -Append -Encoding utf8
    exit $FullBackupExitCode
}
exit $ExitCode
