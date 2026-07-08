$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

& $python -m pytest
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$appJs = Join-Path $projectRoot "webapp\infonalia_webapp\static\app.js"
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check $appJs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Node.js no esta disponible; se omite node --check."
}
