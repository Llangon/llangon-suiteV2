param(
    [int]$MinIdleSeconds = 120,
    [bool]$SkipIfUserActive = $true,
    [bool]$AutoSleep = $true,
    [string]$LogPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-AgendaWakeLog {
    param([string]$Message)
    $Line = "[$(Get-Date -Format s)] $Message"
    if ($LogPath) {
        $Parent = Split-Path -Parent $LogPath
        if ($Parent) {
            New-Item -ItemType Directory -Force -Path $Parent | Out-Null
        }
        $Line | Out-File -FilePath $LogPath -Append -Encoding utf8
    }
    Write-Host $Line
}

if (-not $AutoSleep) {
    Write-AgendaWakeLog "Suspension automatica desactivada por configuracion."
    exit 0
}

$NativeCode = @"
using System;
using System.Runtime.InteropServices;

public static class LlangonPower {
    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }

    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

    [DllImport("kernel32.dll")]
    public static extern uint GetTickCount();

    [DllImport("powrprof.dll", SetLastError=true)]
    public static extern bool SetSuspendState(bool hibernate, bool forceCritical, bool disableWakeEvent);

    public static int IdleSeconds() {
        LASTINPUTINFO info = new LASTINPUTINFO();
        info.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(typeof(LASTINPUTINFO));
        if (!GetLastInputInfo(ref info)) {
            return -1;
        }
        uint tick = GetTickCount();
        return (int)((tick - info.dwTime) / 1000);
    }
}
"@

try {
    Add-Type -TypeDefinition $NativeCode -ErrorAction Stop
}
catch {
    Write-AgendaWakeLog "No se pudo preparar la suspension segura: $($_.Exception.Message)"
    if ($SkipIfUserActive) {
        Write-AgendaWakeLog "Suspension omitida: no se pudo comprobar actividad del usuario."
        exit 0
    }
    exit 1
}

$IdleSeconds = [LlangonPower]::IdleSeconds()
if ($IdleSeconds -lt 0) {
    Write-AgendaWakeLog "No se pudo comprobar inactividad del usuario."
    if ($SkipIfUserActive) {
        Write-AgendaWakeLog "Suspension omitida: no se pudo comprobar actividad del usuario."
        exit 0
    }
}
elseif ($SkipIfUserActive -and $IdleSeconds -lt $MinIdleSeconds) {
    Write-AgendaWakeLog "Suspension omitida: usuario activo. Inactividad detectada: $IdleSeconds segundo(s)."
    exit 0
}
else {
    Write-AgendaWakeLog "Inactividad detectada: $IdleSeconds segundo(s)."
}

Write-AgendaWakeLog "Solicitando suspension normal de Windows."
$Suspended = [LlangonPower]::SetSuspendState($false, $false, $false)
if (-not $Suspended) {
    Write-AgendaWakeLog "Windows rechazo la solicitud de suspension."
    exit 1
}

Write-AgendaWakeLog "Solicitud de suspension enviada correctamente."
exit 0
