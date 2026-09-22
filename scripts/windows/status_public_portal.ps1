Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Port = if ($env:LLANGON_PUBLIC_PORTAL_PORT) { [int]$env:LLANGON_PUBLIC_PORTAL_PORT } else { 8790 }
$HealthUrl = "http://127.0.0.1:$Port/api/health"
try {
    $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
    Write-Host "Portal público: saludable en $HealthUrl"
} catch { Write-Host "Portal público: no responde en $HealthUrl" }
$Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Listener) { Write-Host "Escucha: $($Listener.LocalAddress):$Port | PID $($Listener.OwningProcess)" }
$Cloudflared = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
if ($Cloudflared) { Write-Host "Cloudflare Tunnel: $($Cloudflared.Status)" } else { Write-Host "Cloudflare Tunnel: no instalado como servicio" }
