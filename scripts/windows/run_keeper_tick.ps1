param(
    [switch]$WakeTick
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$LockDir = Join-Path $RuntimeRoot "locks"
New-Item -ItemType Directory -Force -Path $LogDir, $LockDir | Out-Null

$LogPath = Join-Path $LogDir "keeper_tick.log"
$LockPath = Join-Path $LockDir "keeper_tick.lock"
$StaleMinutes = 180
$Port = 8787
$HealthUrl = "http://127.0.0.1:$Port/api/health"
$Source = if ($WakeTick) { "wake_tick" } else { "keeper_tick" }

function Write-KeeperLog {
    param([string]$Message)
    $Line = "[$(Get-Date -Format s)] $Message"
    try {
        $Line | Out-File -LiteralPath $LogPath -Append -Encoding utf8 -ErrorAction Stop
    }
    catch {
        Write-Host $Line
    }
}

function Import-LlangonEnvFile {
    $EnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env"
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
        $Trimmed = $Line.Trim()
        if ($Trimmed -eq "" -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) {
            continue
        }
        $Key, $Value = $Trimmed.Split("=", 2)
        if ($Key.Trim() -eq "INFONALIA_PORT") {
            $Parsed = 0
            if ([int]::TryParse($Value.Trim().Trim('"').Trim("'"), [ref]$Parsed)) {
                $script:Port = $Parsed
                $script:HealthUrl = "http://127.0.0.1:$script:Port/api/health"
            }
        }
    }
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

function Wait-WebHealth {
    param([int]$Seconds = 45)
    $Deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $Deadline) {
        if (Test-WebHealth) {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

Import-LlangonEnvFile

if (Test-Path -LiteralPath $LockPath) {
    $LockAge = (Get-Date) - (Get-Item -LiteralPath $LockPath).LastWriteTime
    if ($LockAge.TotalMinutes -lt $StaleMinutes) {
        Write-KeeperLog "skipped: already running"
        exit 0
    }
    try {
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction Stop
        Write-KeeperLog "Candado huerfano eliminado."
    }
    catch {
        Write-KeeperLog "skipped: already running (lock no eliminable)"
        exit 0
    }
}

try {
    New-Item -ItemType File -Path $LockPath -Force -ErrorAction Stop | Out-Null
}
catch {
    Write-KeeperLog "skipped: already running (lock ocupado)"
    exit 0
}
try {
    Set-Location -LiteralPath $ProjectRoot
    Write-KeeperLog "Tick iniciado. Source=$Source"

    if (-not (Test-WebHealth)) {
        $StartScript = Join-Path $ScriptRoot "start_web_production.ps1"
        Write-KeeperLog "Web no responde. Lanzando start_web_production.ps1 en segundo plano."
        Start-Process powershell.exe `
            -ArgumentList @("-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $StartScript) `
            -WindowStyle Hidden `
            -WorkingDirectory $ProjectRoot | Out-Null
        if (-not (Wait-WebHealth -Seconds 60)) {
            Write-KeeperLog "ERROR: la web no responde tras intentar arrancarla."
            exit 2
        }
    }
    else {
        Write-KeeperLog "Web OK."
    }

    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        $Python = "python"
    }

    Write-KeeperLog "Ejecutando tick interno del scheduler."
    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $TickOutput = & $Python -m webapp.infonalia_webapp.monitor.scheduler --tick --source $Source 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    foreach ($Line in $TickOutput) {
        "$Line" | Out-File -LiteralPath $LogPath -Append -Encoding utf8
    }
    if ($null -eq $ExitCode) {
        $ExitCode = 0
    }
    Write-KeeperLog "Tick finalizado. ExitCode=$ExitCode"
    exit $ExitCode
}
catch {
    Write-KeeperLog "ERROR: $($_.Exception.Message)"
    exit 1
}
finally {
    if (Test-Path -LiteralPath $LockPath) {
        Remove-Item -LiteralPath $LockPath -Force
    }
}
