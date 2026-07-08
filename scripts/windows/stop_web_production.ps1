Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$PidPath = Join-Path $RuntimeRoot "web.pid"
$LogPath = Join-Path $LogDir "web.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-WebLog {
    param([string]$Message)
    $Line = "[$(Get-Date -Format s)] $Message"
    try {
        $Line | Out-File -LiteralPath $LogPath -Append -Encoding utf8 -ErrorAction Stop
    }
    catch {
        Write-Host $Line
    }
}

function Stop-IfLlangonWebProcess {
    param(
        [int]$TargetPid,
        [switch]$TrustedSource
    )
    $Process = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return $false
    }
    $Cim = Get-CimInstance Win32_Process -Filter "ProcessId=$TargetPid" -ErrorAction SilentlyContinue
    $CommandLine = if ($Cim) { [string]$Cim.CommandLine } else { "" }
    $LooksLikeSuiteWeb = (
        $CommandLine -like "*Llangon-SuiteV2*" -or
        $CommandLine -like "*webapp.infonalia_webapp.serve*"
    )
    if (-not $LooksLikeSuiteWeb -and -not $TrustedSource) {
        Write-WebLog "No se detiene PID ${TargetPid}: no parece web de Llangon Suite."
        return $false
    }
    Write-WebLog "Deteniendo web Llangon Suite PID $TargetPid."
    Stop-Process -Id $TargetPid -Force
    return $true
}

$Stopped = $false
if (Test-Path -LiteralPath $PidPath) {
    $RecordedPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($RecordedPid -and ($RecordedPid -as [int])) {
        $Stopped = Stop-IfLlangonWebProcess -TargetPid ([int]$RecordedPid) -TrustedSource
    }
}

if (-not $Stopped) {
    $Listeners = @(Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)
    foreach ($Listener in $Listeners) {
        if (Stop-IfLlangonWebProcess -TargetPid ([int]$Listener.OwningProcess) -TrustedSource) {
            $Stopped = $true
        }
    }
}

if ($Stopped -and (Test-Path -LiteralPath $PidPath)) {
    Remove-Item -LiteralPath $PidPath -Force
}

if ($Stopped) {
    Write-Host "Web Llangon Suite detenida."
}
else {
    Write-Host "No se encontró un proceso web de Llangon Suite para detener."
}
