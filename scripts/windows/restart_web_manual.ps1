Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$PidPath = Join-Path $RuntimeRoot "web.pid"
$EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"
$StatusScript = Join-Path $ScriptRoot "status_local_deployment.ps1"
$StartScript = Join-Path $ScriptRoot "start_web_production.ps1"
$Port = 8787

if (Test-Path -LiteralPath $EnvPath) {
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        $Value = $Value.Trim().Trim('"').Trim("'")
        if ($Key -eq "INFONALIA_PORT" -and $Value) {
            $ParsedPort = 0
            if ([int]::TryParse($Value, [ref]$ParsedPort)) {
                $Port = $ParsedPort
            }
        }
    }
}

$HealthUrl = "http://127.0.0.1:$Port/api/health"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message
}

function Test-WebHealth {
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
        return ($Response.StatusCode -eq 200 -and $Response.Content -like '*"status": "ok"*')
    }
    catch {
        return $false
    }
}

function Get-WebListeners {
    try {
        return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    catch {
        return @()
    }
}

function Describe-Process {
    param([int]$ProcessId)
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return "PID $ProcessId (proceso no encontrado)"
    }
    return "PID $ProcessId ($($Process.ProcessName))"
}

function Test-IsLlangonWebProcess {
    param(
        [int]$ProcessId,
        [switch]$TrustedSource
    )
    if ($TrustedSource) {
        return $true
    }
    $Cim = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    $CommandLine = if ($Cim) { [string]$Cim.CommandLine } else { "" }
    return (
        $CommandLine -like "*Llangon-SuiteV2*" -or
        $CommandLine -like "*webapp.infonalia_webapp.serve*" -or
        $CommandLine -like "*start_web_production.ps1*"
    )
}

function Stop-LlangonWebProcess {
    param(
        [int]$ProcessId,
        [switch]$TrustedSource
    )
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return $false
    }
    if (-not (Test-IsLlangonWebProcess -ProcessId $ProcessId -TrustedSource:$TrustedSource)) {
        Write-Host "No se detiene $(Describe-Process -ProcessId $ProcessId): no parece web de Llangon Suite."
        return $false
    }
    Write-Host "Deteniendo proceso web: $(Describe-Process -ProcessId $ProcessId)"
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    return $true
}

function Stop-ListenerProcesses {
    $Listeners = @(Get-WebListeners)
    if ($Listeners.Count -eq 0) {
        return @()
    }

    $StoppedPids = New-Object System.Collections.Generic.List[int]
    $Pids = @($Listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ProcessId in $Pids) {
        if (-not $ProcessId) {
            continue
        }
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $Process) {
            continue
        }
        if (Stop-LlangonWebProcess -ProcessId $ProcessId) {
            [void]$StoppedPids.Add($ProcessId)
        }
    }
    return @($StoppedPids | Select-Object -Unique)
}

function Stop-RecordedPid {
    param(
        [int[]]$AlreadyStoppedPids = @()
    )
    if (-not (Test-Path -LiteralPath $PidPath)) {
        return $false
    }
    $RecordedPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $RecordedPid) {
        return $false
    }
    $ParsedPid = 0
    if (-not [int]::TryParse($RecordedPid, [ref]$ParsedPid)) {
        return $false
    }
    if ($AlreadyStoppedPids -contains $ParsedPid) {
        return $true
    }
    $Process = Get-Process -Id $ParsedPid -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return $false
    }
    return Stop-LlangonWebProcess -ProcessId $ParsedPid -TrustedSource
}

function Wait-UntilStopped {
    param([int]$TimeoutSeconds = 20)
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if (-not (Test-WebHealth) -and @(Get-WebListeners).Count -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-UntilHealthy {
    param([int]$TimeoutSeconds = 45)
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if (Test-WebHealth) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "Proyecto: $ProjectRoot"
Write-Host "URL:      $HealthUrl"

Write-Step "[1/3] Deteniendo web actual si existe..."
$StoppedSomething = $false
$StoppedPids = @(Stop-ListenerProcesses)

if ($StoppedPids.Count -gt 0) {
    $StoppedSomething = $true
}

if (Stop-RecordedPid -AlreadyStoppedPids $StoppedPids) {
    $StoppedSomething = $true
}

if (-not $StoppedSomething) {
    Write-Host "No habia proceso web activo."
}

if (-not (Wait-UntilStopped -TimeoutSeconds 20)) {
    Write-Host "ERROR: no se pudo liberar el puerto $Port."
    $Listeners = @(Get-WebListeners)
    foreach ($Listener in $Listeners) {
        Write-Host "Sigue escuchando: $($Listener.LocalAddress):$Port | $(Describe-Process -ProcessId $Listener.OwningProcess)"
    }
    exit 2
}

Write-Step "[2/3] Arrancando web en segundo plano..."
if (-not (Test-Path -LiteralPath $StartScript)) {
    Write-Host "ERROR: no se encuentra start_web_production.ps1."
    exit 3
}

Start-Process powershell.exe `
    -ArgumentList @("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $StartScript) `
    -WindowStyle Hidden `
    -WorkingDirectory $ProjectRoot | Out-Null
Write-Host "Proceso iniciado. Esperando healthcheck..."

if (-not (Wait-UntilHealthy -TimeoutSeconds 45)) {
    Write-Host "ERROR: la web no respondio al healthcheck tras el reinicio."
    $WebLog = Join-Path $LogDir "web.log"
    if (Test-Path -LiteralPath $WebLog) {
        Write-Host ""
        Write-Host "Ultimas lineas de web.log:"
        Get-Content -LiteralPath $WebLog -Tail 20
    }
    exit 4
}

Write-Step "[3/3] Comprobando estado..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StatusScript

exit 0
