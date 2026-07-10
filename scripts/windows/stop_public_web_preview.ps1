$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$PublicRoot = Join-Path $ProjectRoot "firebase\public_firebase"
$PreviewServer = Join-Path $ProjectRoot "scripts\public_web_preview_server.py"
$PreviewStateDir = Join-Path ([System.IO.Path]::GetTempPath()) "LlangonSuite\public_web_preview"
$PidFile = Join-Path $PreviewStateDir "public_web_preview.pid"
$Port = 5500

function Test-PreviewCommandLine {
    param([int]$ProcessId)

    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        $commandLine = [string]$processInfo.CommandLine
        return (
            $commandLine -match [regex]::Escape($PreviewServer) -and
            $commandLine -match [regex]::Escape($PublicRoot)
        )
    } catch {
        return $false
    }
}

function Stop-PreviewProcessById {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        if (-not (Test-PreviewCommandLine -ProcessId $ProcessId)) {
            Write-Host "El PID $ProcessId no parece ser la vista previa publica de este repo. No se detiene."
            return $false
        }

        Stop-Process -Id $ProcessId -Force
        Write-Host "Vista previa detenida. PID: $ProcessId"
        return $true
    }

    return $false
}

$stopped = $false

if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
    $rawPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $parsedPid = 0
    if ([int]::TryParse($rawPid, [ref]$parsedPid)) {
        $stopped = Stop-PreviewProcessById -ProcessId $parsedPid
    }
    Remove-Item -LiteralPath $PidFile -Force
}

if (-not $stopped) {
    try {
        $listener = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($listener) {
            if (Test-PreviewCommandLine -ProcessId $listener.OwningProcess) {
                $stopped = Stop-PreviewProcessById -ProcessId $listener.OwningProcess
            } else {
                Write-Host "El puerto $Port esta ocupado por otro proceso. No se detiene automaticamente. PID: $($listener.OwningProcess)"
            }
        }
    } catch {
        Write-Host "No se pudo consultar el puerto $Port."
    }
}

if (-not $stopped) {
    Write-Host "No habia una vista previa publica activa registrada."
}
