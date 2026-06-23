Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"

Write-Host "Proyecto: $ProjectRoot"
Write-Host "Logs:     $LogDir"
Write-Host ""

$TaskNames = @(
    "LlangonSuite-Web",
    "LlangonSuite-Scheduler",
    "LlangonSuite-Backup"
)

foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        Write-Host "$TaskName : no instalada"
    }
    else {
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "$TaskName : $($Task.State) | ultima ejecucion: $($Info.LastRunTime) | resultado: $($Info.LastTaskResult)"
    }
}

Write-Host ""
try {
    $Response = Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "Healthcheck web: $($Response.StatusCode) $($Response.Content)"
}
catch {
    Write-Host "Healthcheck web: no responde en http://127.0.0.1:8787/api/health"
}

Write-Host ""
foreach ($LogName in @("web.log", "scheduler.log", "backup.log")) {
    $LogPath = Join-Path $LogDir $LogName
    if (Test-Path -LiteralPath $LogPath) {
        $Item = Get-Item -LiteralPath $LogPath
        Write-Host "$LogName : $($Item.Length) bytes | $($Item.LastWriteTime)"
    }
    else {
        Write-Host "$LogName : no existe todavia"
    }
}

Write-Host ""
$Cloudflared = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
if ($null -eq $Cloudflared) {
    Write-Host "Cloudflare Tunnel: no instalado como servicio en este equipo."
}
else {
    Write-Host "Cloudflare Tunnel: $($Cloudflared.Status)"
}

