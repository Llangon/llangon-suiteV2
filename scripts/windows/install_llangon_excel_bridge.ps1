param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$module = Join-Path $repoRoot "webapp\infonalia_webapp\tender_documents\bridge.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encuentra el entorno Python de Llangon Suite: $python"
}
if (-not (Test-Path -LiteralPath $module)) {
    throw "No se encuentra el bridge de Ficha Llangon v2."
}

$targetDir = Join-Path $env:LOCALAPPDATA "LlangonSuite\bridge"
$target = Join-Path $targetDir "llangon-excel-bridge.cmd"
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$content = @"
@echo off
setlocal
set "LLANGON_REPO_ROOT=$repoRoot"
set "LLANGON_PYTHON=$python"
if not exist "%LLANGON_PYTHON%" exit /b 20
pushd "%LLANGON_REPO_ROOT%" >nul
"%LLANGON_PYTHON%" -m webapp.infonalia_webapp.tender_documents.bridge %*
set "LLANGON_EXIT=%ERRORLEVEL%"
popd >nul
exit /b %LLANGON_EXIT%
"@

Set-Content -LiteralPath $target -Value $content -Encoding Ascii
Write-Host "Bridge instalado en: $target"
Write-Host "Repositorio configurado: $repoRoot"
