Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$PidPath = Join-Path $ProjectRoot "runtime\public_portal.pid"
if (-not (Test-Path -LiteralPath $PidPath)) { Write-Host "No hay PID registrado para el portal público."; exit 0 }
$ProcessId = [int](Get-Content -LiteralPath $PidPath | Select-Object -First 1)
$Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
if ($null -ne $Process) {
    $Details = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $Details -or [string]$Details.CommandLine -notlike "*public_portal_server.app*") { throw "El PID registrado no parece pertenecer al portal público; no se detiene." }
    Stop-Process -Id $ProcessId -Force
}
Remove-Item -LiteralPath $PidPath -Force
Write-Host "Portal público detenido."
