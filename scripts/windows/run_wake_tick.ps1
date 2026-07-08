Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$KeeperScript = Join-Path $ScriptRoot "run_keeper_tick.ps1"

& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $KeeperScript -WakeTick
exit $LASTEXITCODE
