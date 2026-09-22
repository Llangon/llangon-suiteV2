Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DevEnvPath = Join-Path $ProjectRoot "webapp\infonalia_webapp\.env.dev"
$DevRoot = Join-Path $ProjectRoot ".llangon-dev"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $DevEnvPath)) {
    throw "Falta $DevEnvPath. Copia .env.dev.example, usa credenciales ficticias y vuelve a ejecutar."
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "No se encontró el entorno virtual en .venv. Créalo e instala requirements-dev.txt antes de arrancar."
}

# .env.dev se carga antes que .env para que sus credenciales ficticias prevalezcan.
foreach ($Line in Get-Content -LiteralPath $DevEnvPath) {
    $Trimmed = $Line.Trim()
    if (-not $Trimmed -or $Trimmed.StartsWith("#") -or -not $Trimmed.Contains("=")) { continue }
    $Key, $Value = $Trimmed.Split("=", 2)
    Set-Item -Path ("Env:" + $Key.Trim()) -Value $Value.Trim().Trim('"').Trim("'")
}

# Aislamiento no negociable: loopback, datos nuevos y ninguna integración real.
$env:INFONALIA_HOST = "127.0.0.1"
$env:INFONALIA_PORT = "8788"
$env:INFONALIA_ALLOW_NON_LOOPBACK = "0"
$env:LLANGON_DATA_ROOT = Join-Path $DevRoot "data"
$env:LLANGON_RUNTIME_ROOT = Join-Path $DevRoot "runtime"
$env:INFONALIA_STORAGE_BACKEND = "local"
$env:LLANGON_DROPBOX_BASE_PATH = Join-Path $DevRoot "dropbox-replica"
$env:INFONALIA_DROPBOX_ROOT = $env:LLANGON_DROPBOX_BASE_PATH
$env:INFONALIA_DOWNLOAD_STAGING_ROOT = Join-Path $DevRoot "downloads"
$env:INFONALIA_DROPBOX_ENABLED = "0"
$env:INFONALIA_DROPBOX_DRY_RUN = "1"
$env:INFONALIA_SMTP_ENABLED = "0"
$env:INFONALIA_EMAIL_DRY_RUN = "1"
$env:LLANGON_TELEGRAM_ENABLED = "0"
$env:LLANGON_EMAIL_ACTIONS_ENABLED = "0"
$env:LLANGON_INFONALIA_IMPORT_ENABLED = "0"
$env:MONITOR_SCHEDULER_ENABLED = "0"
$env:MONITOR_LICITACIONES_SCHEDULE_ENABLED = "0"
$env:MONITOR_LICITACIONES_REAL_ENABLED = "0"
$env:LLANGON_FULL_BACKUP_ENABLED = "0"
$env:CODEX_LOCAL_ENABLED = "false"
$env:GEMINI_ENABLED = "false"
$env:LLANGON_PUBLIC_PORTAL_HOST = "127.0.0.1"
$env:LLANGON_PUBLIC_PORTAL_PORT = "8791"
$env:LLANGON_PORTAL_BASE_URL = "http://127.0.0.1:8791"
$env:LLANGON_PUBLIC_PORTAL_URL = ""

New-Item -ItemType Directory -Force -Path $env:LLANGON_DATA_ROOT, $env:LLANGON_RUNTIME_ROOT, $env:LLANGON_DROPBOX_BASE_PATH, $env:INFONALIA_DOWNLOAD_STAGING_ROOT | Out-Null
Set-Location -LiteralPath $ProjectRoot
Write-Host "Entorno de desarrollo aislado: http://127.0.0.1:8788"
Write-Host "Datos y logs: $DevRoot"
& $Python -m webapp.infonalia_webapp.serve
