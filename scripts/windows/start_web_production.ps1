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

$HostAddress = "127.0.0.1"
$Port = 8787
$AllowNonLoopback = $false
$EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"
if (Test-Path -LiteralPath $EnvPath) {
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        $Value = $Value.Trim().Trim('"').Trim("'")
        if ($Key -eq "INFONALIA_HOST" -and $Value) {
            $HostAddress = $Value
        }
        elseif ($Key -eq "INFONALIA_PORT" -and $Value) {
            $ParsedPort = 0
            if ([int]::TryParse($Value, [ref]$ParsedPort)) {
                $Port = $ParsedPort
            }
        }
        elseif ($Key -eq "INFONALIA_ALLOW_NON_LOOPBACK" -and $Value) {
            $AllowNonLoopback = @("1", "true", "yes", "on", "si", "sí") -contains $Value.ToLowerInvariant()
        }
    }
}

$LogPath = Join-Path $LogDir "web.log"
$StdoutPath = Join-Path $LogDir "web.stdout.log"
$StderrPath = Join-Path $LogDir "web.stderr.log"
$PidPath = Join-Path $RuntimeRoot "web.pid"
$LockPath = Join-Path $LockDir "web.lock"
$HealthUrl = "http://127.0.0.1:$Port/api/health"

function Write-WebLog {
    param([string]$Message)
    $Line = "[$(Get-Date -Format s)] $Message"
    try {
        $Line | Out-File -FilePath $LogPath -Append -Encoding utf8 -ErrorAction Stop
    }
    catch {
        Write-Host $Line
    }
}

trap {
    Write-WebLog "ERROR PowerShell en start_web_production.ps1: $($_.Exception.Message)"
    exit 99
}

function Test-WebHealth {
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return ($Response.StatusCode -eq 200 -and $Response.Content -like '*"status": "ok"*')
    }
    catch {
        return $false
    }
}

function Get-WebListener {
    try {
        return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    catch {
        return $null
    }
}

function Test-CanAppendFile {
    param([string]$Path)
    try {
        $Stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
        $Stream.Close()
        return $true
    }
    catch {
        return $false
    }
}

function Resolve-LogOutputPath {
    param(
        [string]$PreferredPath,
        [string]$Prefix
    )
    if (Test-CanAppendFile -Path $PreferredPath) {
        return $PreferredPath
    }
    $AlternativePath = Join-Path $LogDir ("{0}.{1}.log" -f $Prefix, $PID)
    if (Test-CanAppendFile -Path $AlternativePath) {
        Write-WebLog "No se puede escribir en $PreferredPath. Usando $AlternativePath."
        return $AlternativePath
    }
    $TempPath = Join-Path $env:TEMP ("{0}.{1}.log" -f $Prefix, $PID)
    Write-WebLog "No se puede escribir en logs runtime. Usando $TempPath."
    return $TempPath
}

Set-Location -LiteralPath $ProjectRoot
Write-WebLog "Arrancando servidor local Llangon Suite..."

if (($HostAddress -ne "127.0.0.1" -and $HostAddress -ne "localhost" -and $HostAddress -ne "0.0.0.0") -or (($HostAddress -eq "0.0.0.0") -and -not $AllowNonLoopback)) {
    if ($HostAddress -eq "0.0.0.0" -and -not $AllowNonLoopback) {
        Write-WebLog "ERROR: INFONALIA_HOST=0.0.0.0 requiere INFONALIA_ALLOW_NON_LOOPBACK=1."
    }
    else {
        Write-WebLog "ERROR: INFONALIA_HOST debe ser 127.0.0.1, localhost o 0.0.0.0. Valor actual: $HostAddress"
    }
    exit 2
}

if (Test-WebHealth) {
    $Listener = Get-WebListener
    if ($null -ne $Listener) {
        Write-WebLog "Servidor ya activo y saludable en $HealthUrl. PID $($Listener.OwningProcess)."
    }
    else {
        Write-WebLog "Servidor ya responde healthcheck en $HealthUrl."
    }
    exit 0
}

$ExistingListener = Get-WebListener
if ($null -ne $ExistingListener) {
    $ProcessName = (Get-Process -Id $ExistingListener.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Write-WebLog "ERROR: Puerto $Port ocupado por PID $($ExistingListener.OwningProcess) ($ProcessName), pero healthcheck no responde."
    exit 3
}

if (Test-Path -LiteralPath $PidPath) {
    $RecordedPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($RecordedPid) {
        $RecordedProcess = Get-Process -Id ([int]$RecordedPid) -ErrorAction SilentlyContinue
        if ($null -eq $RecordedProcess) {
            Write-WebLog "PID registrado huerfano eliminado: $RecordedPid."
            Remove-Item -LiteralPath $PidPath -Force
        }
    }
}

if (Test-Path -LiteralPath $LockPath) {
    $LockAge = (Get-Date) - (Get-Item -LiteralPath $LockPath).LastWriteTime
    if ($LockAge.TotalSeconds -gt 60) {
        Write-WebLog "Candado web huerfano eliminado: $LockPath."
        Remove-Item -LiteralPath $LockPath -Force
    }
    else {
        Write-WebLog "ERROR: existe un candado web reciente y no hay healthcheck. Puede haber un arranque en curso."
        exit 6
    }
}

Write-WebLog "Ejecutando proceso web en primer plano. El healthcheck posterior lo realiza serve.py."
$StdoutPath = Resolve-LogOutputPath -PreferredPath $StdoutPath -Prefix "web.stdout"
$StderrPath = Resolve-LogOutputPath -PreferredPath $StderrPath -Prefix "web.stderr"
$PreviousErrorActionPreference = $ErrorActionPreference
$HasNativeErrorPreference = Test-Path -LiteralPath Variable:\PSNativeCommandUseErrorActionPreference
$PreviousNativeErrorPreference = if ($HasNativeErrorPreference) { $PSNativeCommandUseErrorActionPreference } else { $null }
try {
    # La salida stderr del servidor (por ejemplo, un BrokenPipe de un cliente que
    # se desconecta) es diagnóstica y nunca debe terminar el wrapper PowerShell.
    $ErrorActionPreference = "Continue"
    if ($HasNativeErrorPreference) {
        $PSNativeCommandUseErrorActionPreference = $false
    }
    & $Python -u -m webapp.infonalia_webapp.serve 1>> $StdoutPath 2>> $StderrPath
    $ExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
    if ($HasNativeErrorPreference) {
        $PSNativeCommandUseErrorActionPreference = $PreviousNativeErrorPreference
    }
}
if ($null -eq $ExitCode) {
    $ExitCode = 0
}
Write-WebLog "Proceso web finalizado. ExitCode $ExitCode."
if (Test-Path -LiteralPath $PidPath) {
    $RecordedPid = Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($RecordedPid) {
        $RecordedProcess = Get-Process -Id ([int]$RecordedPid) -ErrorAction SilentlyContinue
        if ($null -eq $RecordedProcess) {
            Remove-Item -LiteralPath $PidPath -Force
            Write-WebLog "PID registrado eliminado tras finalizar: $RecordedPid."
        }
    }
}
if ((Test-Path -LiteralPath $LockPath) -and -not (Get-WebListener)) {
    Remove-Item -LiteralPath $LockPath -Force
    Write-WebLog "Candado web eliminado tras finalizar."
}
exit $ExitCode
