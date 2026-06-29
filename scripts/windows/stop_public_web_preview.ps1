$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$RuntimeDir = Join-Path $ProjectRoot "runtime"
$PidFile = Join-Path $RuntimeDir "public_web_preview.pid"
$Port = 5500

function Stop-PreviewProcessById {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
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
            $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)").CommandLine
            if ($commandLine -match "http\.server" -and $commandLine -match [regex]::Escape("firebase\public_firebase")) {
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
