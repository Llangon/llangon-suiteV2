Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }
$EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$PidPath = Join-Path $RuntimeRoot "public_portal.pid"
$Port = 8790

if (Test-Path -LiteralPath $EnvPath) {
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) { continue }
        $Key, $Value = $Trimmed.Split("=", 2)
        $Key = $Key.Trim()
        $Value = $Value.Trim().Trim('"').Trim("'")
        if ($Key.StartsWith("LLANGON_") -and $Value) { [Environment]::SetEnvironmentVariable($Key, $Value, "Process") }
    }
}
if ($env:LLANGON_PUBLIC_PORTAL_PORT) {
    $ParsedPort = 0
    if ([int]::TryParse($env:LLANGON_PUBLIC_PORTAL_PORT, [ref]$ParsedPort)) { $Port = $ParsedPort }
}

$HealthUrl = "http://127.0.0.1:$Port/api/health"
try {
    $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
    if ($Response.StatusCode -eq 200) { Write-Host "Portal público ya activo en $HealthUrl"; exit 0 }
} catch {}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stdout = Join-Path $LogDir "public_portal.stdout.log"
$Stderr = Join-Path $LogDir "public_portal.stderr.log"
$Process = Start-Process -FilePath $Python -ArgumentList @("-m", "public_portal_server.app") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru
$Process.Id | Out-File -LiteralPath $PidPath -Encoding ascii

for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        if ($Response.StatusCode -eq 200) { Write-Host "Portal público iniciado en $HealthUrl (PID $($Process.Id))."; exit 0 }
    } catch {}
    if ($Process.HasExited) { break }
}
throw "El portal público no superó el healthcheck. Revisa public_portal.stderr.log."
