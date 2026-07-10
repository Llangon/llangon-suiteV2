$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$PublicRoot = Join-Path $ProjectRoot "firebase\public_firebase"
$PreviewServer = Join-Path $ProjectRoot "scripts\public_web_preview_server.py"
$Port = 5500
$Url = "http://127.0.0.1:$Port/"
$ContactUrl = "http://127.0.0.1:$Port/contacto"
$PreviewStateDir = Join-Path ([System.IO.Path]::GetTempPath()) "LlangonSuite\public_web_preview"
$LogDir = $PreviewStateDir
$PidFile = Join-Path $PreviewStateDir "public_web_preview.pid"
$StdoutLog = Join-Path $LogDir "public_web_preview.log"
$StderrLog = Join-Path $LogDir "public_web_preview.err.log"

function Test-PreviewHealth {
    param(
        [string]$ExpectedText = "ASESORES LLANGON"
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return (
            $response.StatusCode -ge 200 -and
            $response.StatusCode -lt 300 -and
            $response.Content -like "*$ExpectedText*"
        )
    } catch {
        return $false
    }
}

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

function Get-PreviewListener {
    try {
        return Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    } catch {
        return $null
    }
}

if (-not (Test-Path -LiteralPath $PublicRoot -PathType Container)) {
    throw "No existe la carpeta publica activa: $PublicRoot"
}

if (-not (Test-Path -LiteralPath $PreviewServer -PathType Leaf)) {
    throw "No existe el servidor local de vista previa: $PreviewServer"
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$listener = Get-PreviewListener
if ($listener) {
    if ((Test-PreviewCommandLine -ProcessId $listener.OwningProcess) -and (Test-PreviewHealth)) {
        Set-Content -LiteralPath $PidFile -Value $listener.OwningProcess -Encoding ASCII
        Write-Host "La web publica ya esta disponible en $Url"
        exit 0
    }

    throw "El puerto $Port esta ocupado por otro proceso o por una vista previa no valida. PID: $($listener.OwningProcess)"
}

$pythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "No se encontro Python para levantar la vista previa."
    }
    $pythonPath = $pythonCommand.Source
}

$arguments = @(
    $PreviewServer,
    "--directory",
    "$PublicRoot",
    "--host",
    "127.0.0.1",
    "--port",
    "$Port"
)

$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList $arguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII

$ok = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) {
        throw "El servidor de vista previa termino antes de responder. Revisa $StderrLog"
    }
    if (Test-PreviewHealth) {
        $ok = $true
        break
    }
}

if (-not $ok) {
    throw "La web publica no respondio en $Url. Revisa $StdoutLog y $StderrLog"
}

try {
    $routeResponse = Invoke-WebRequest -Uri $ContactUrl -UseBasicParsing -TimeoutSec 2
    if (
        $routeResponse.StatusCode -lt 200 -or
        $routeResponse.StatusCode -ge 300 -or
        $routeResponse.Content -notlike "*Contacto*"
    ) {
        throw "La ruta /contacto no respondio correctamente."
    }
} catch {
    throw "La vista previa no esta resolviendo rutas como Firebase. Revisa $StderrLog"
}

Write-Host "Web publica disponible en $Url"
Write-Host "Carpeta servida: $PublicRoot"
