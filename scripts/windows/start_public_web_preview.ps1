$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$PublicRoot = Join-Path $ProjectRoot "firebase\public_firebase"
$Port = 5500
$Url = "http://127.0.0.1:$Port/"
$RuntimeDir = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PidFile = Join-Path $RuntimeDir "public_web_preview.pid"
$StdoutLog = Join-Path $LogDir "public_web_preview.log"
$StderrLog = Join-Path $LogDir "public_web_preview.err.log"

function Test-PreviewHealth {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
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

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$listener = Get-PreviewListener
if ($listener) {
    if (Test-PreviewHealth) {
        Set-Content -LiteralPath $PidFile -Value $listener.OwningProcess -Encoding ASCII
        Write-Host "La web publica ya esta disponible en $Url"
        exit 0
    }

    throw "El puerto $Port esta ocupado, pero la web publica no responde en $Url. PID: $($listener.OwningProcess)"
}

$pythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "No se encontro Python para levantar la vista previa."
    }
    $pythonPath = $pythonCommand.Source
}

$pythonWindowlessPath = Join-Path (Split-Path -Parent $pythonPath) "pythonw.exe"
if (Test-Path -LiteralPath $pythonWindowlessPath -PathType Leaf) {
    $pythonPath = $pythonWindowlessPath
}

$arguments = @(
    "-m",
    "http.server",
    "$Port",
    "--bind",
    "127.0.0.1",
    "--directory",
    "$PublicRoot"
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

Write-Host "Web publica disponible en $Url"
Write-Host "Carpeta servida: $PublicRoot"
