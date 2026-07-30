$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$systemTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$pytestBaseTemp = Join-Path $systemTempRoot ("llangon-pytest-" + [Guid]::NewGuid().ToString("N"))
& $python -m pytest --basetemp $pytestBaseTemp
$pytestExitCode = $LASTEXITCODE

if (Test-Path -LiteralPath $pytestBaseTemp) {
    $resolvedBaseTemp = [IO.Path]::GetFullPath($pytestBaseTemp)
    $expectedPrefix = $systemTempRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $leafName = [IO.Path]::GetFileName($resolvedBaseTemp)
    if (
        $resolvedBaseTemp.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        $leafName.StartsWith("llangon-pytest-", [StringComparison]::Ordinal)
    ) {
        try {
            Remove-Item -LiteralPath $resolvedBaseTemp -Recurse -Force
        } catch {
            Write-Warning "No se pudo limpiar el temporal aislado de pytest: $resolvedBaseTemp"
        }
    } else {
        throw "Se rechazó limpiar una ruta temporal no reconocida: $resolvedBaseTemp"
    }
}

if ($pytestExitCode -ne 0) {
    exit $pytestExitCode
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
