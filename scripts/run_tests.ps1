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

if (Get-Command node -ErrorAction SilentlyContinue) {
    $javascriptFiles = @(
        "webapp\infonalia_webapp\static\app.js",
        "webapp\infonalia_webapp\static\tender_monitor.js",
        "webapp\infonalia_webapp\static\login.js",
        "firebase\public_firebase\static\public.js"
    )
    foreach ($relativePath in $javascriptFiles) {
        node --check (Join-Path $projectRoot $relativePath)
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
} else {
    Write-Host "Node.js no esta disponible; se omite node --check."
}
