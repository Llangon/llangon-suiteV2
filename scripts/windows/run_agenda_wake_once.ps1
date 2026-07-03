Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
$RuntimeRoot = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$LockDir = Join-Path $RuntimeRoot "locks"
New-Item -ItemType Directory -Force -Path $LogDir, $LockDir | Out-Null

$LogPath = Join-Path $LogDir "agenda_wake.log"
$LockPath = Join-Path $LockDir "agenda_wake.lock"
$StaleMinutes = 180

function Write-AgendaWakeLog {
    param([string]$Message)
    "[$(Get-Date -Format s)] $Message" | Out-File -FilePath $LogPath -Append -Encoding utf8
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
        $Key = $Key.Trim()
        if (-not $Key) {
            continue
        }
        if ([Environment]::GetEnvironmentVariable($Key, "Process")) {
            continue
        }
        [Environment]::SetEnvironmentVariable($Key, $Value.Trim().Trim('"').Trim("'"), "Process")
    }
}

function Get-EnvBool {
    param([string]$Name, [bool]$Default)
    $Raw = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($null -eq $Raw -or $Raw.Trim() -eq "") {
        return $Default
    }
    return @("1", "true", "yes", "on", "si", "sí") -contains $Raw.Trim().ToLowerInvariant()
}

function Get-EnvInt {
    param([string]$Name, [int]$Default, [int]$Minimum = 1)
    $Raw = [Environment]::GetEnvironmentVariable($Name, "Process")
    $Parsed = 0
    if ($Raw -and [int]::TryParse($Raw, [ref]$Parsed) -and $Parsed -ge $Minimum) {
        return $Parsed
    }
    return $Default
}

function Format-ExitCode {
    param($Code)
    if ($null -eq $Code) {
        return 0
    }
    return [int]$Code
}

Import-LlangonEnvFile

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

if (Test-Path -LiteralPath $LockPath) {
    $LockAge = (Get-Date) - (Get-Item -LiteralPath $LockPath).LastWriteTime
    if ($LockAge.TotalMinutes -lt $StaleMinutes) {
        Write-AgendaWakeLog "AgendaWake omitida: ejecucion anterior todavia activa."
        exit 0
    }
    Remove-Item -LiteralPath $LockPath -Force
}

New-Item -ItemType File -Path $LockPath -Force | Out-Null
$Started = Get-Date
$ExitCode = 0

try {
    Set-Location -LiteralPath $ProjectRoot
    Write-AgendaWakeLog "Iniciando AgendaWake."
    Write-AgendaWakeLog "Tarea de negocio usada: agenda_pendientes_diaria."

    $PreviousEnv = @{
        "LLANGON_INFONALIA_IMPORT_ENABLED" = $env:LLANGON_INFONALIA_IMPORT_ENABLED
        "LLANGON_EMAIL_ACTIONS_ENABLED" = $env:LLANGON_EMAIL_ACTIONS_ENABLED
        "LLANGON_FILE_INVENTORY_ENABLED" = $env:LLANGON_FILE_INVENTORY_ENABLED
        "MONITOR_LICITACIONES_SCHEDULE_ENABLED" = $env:MONITOR_LICITACIONES_SCHEDULE_ENABLED
        "MONITOR_AGENDA_PENDING_DAILY_ENABLED" = $env:MONITOR_AGENDA_PENDING_DAILY_ENABLED
    }

    $env:LLANGON_INFONALIA_IMPORT_ENABLED = "0"
    $env:LLANGON_EMAIL_ACTIONS_ENABLED = "0"
    $env:LLANGON_FILE_INVENTORY_ENABLED = "0"
    $env:MONITOR_LICITACIONES_SCHEDULE_ENABLED = "0"
    $env:MONITOR_AGENDA_PENDING_DAILY_ENABLED = "1"

    try {
        Write-AgendaWakeLog "Ejecutando scheduler solo con Agenda pendiente habilitada."
        & $Python -m webapp.infonalia_webapp.monitor.scheduler --once 2>&1 | ForEach-Object {
            $_ | Out-File -FilePath $LogPath -Append -Encoding utf8
        }
        $ExitCode = Format-ExitCode $LASTEXITCODE
    }
    finally {
        foreach ($Key in $PreviousEnv.Keys) {
            [Environment]::SetEnvironmentVariable($Key, $PreviousEnv[$Key], "Process")
        }
    }

    $Duration = [int]((Get-Date) - $Started).TotalSeconds
    if ($ExitCode -ne 0) {
        Write-AgendaWakeLog "AgendaWake termino con error. Codigo: $ExitCode. Duracion: $Duration segundo(s). No se suspende el equipo."
        exit $ExitCode
    }

    Write-AgendaWakeLog "AgendaWake completada correctamente. Duracion: $Duration segundo(s)."
    Start-Sleep -Seconds 10

    $AutoSleep = Get-EnvBool "LLANGON_AGENDA_WAKE_AUTO_SLEEP" $true
    $SkipIfUserActive = Get-EnvBool "LLANGON_AGENDA_WAKE_SKIP_SLEEP_IF_USER_ACTIVE" $true
    $MinIdleSeconds = Get-EnvInt "LLANGON_AGENDA_WAKE_MIN_IDLE_SECONDS" 120 0
    $SuspendScript = Join-Path $ScriptRoot "suspend_windows.ps1"

    & powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $SuspendScript `
        -MinIdleSeconds $MinIdleSeconds `
        -SkipIfUserActive $SkipIfUserActive `
        -AutoSleep $AutoSleep `
        -LogPath $LogPath
    exit (Format-ExitCode $LASTEXITCODE)
}
catch {
    Write-AgendaWakeLog "AgendaWake fallo: $($_.Exception.Message). No se suspende el equipo."
    exit 1
}
finally {
    if (Test-Path -LiteralPath $LockPath) {
        Remove-Item -LiteralPath $LockPath -Force
    }
}
