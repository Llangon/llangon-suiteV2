@echo off
setlocal

REM ============================================================
REM Reinicio manual de Llangon Suite Web
REM Ubicacion recomendada:
REM scripts\windows\restart_web_manual.bat
REM ============================================================

set "PROJECT_ROOT=%~dp0..\.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"

echo.
echo ============================================================
echo Reiniciando Llangon Suite Web
echo Proyecto: %PROJECT_ROOT%
echo ============================================================
echo.

echo [1/3] Deteniendo proceso web en 127.0.0.1:8787 si existe...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$conns = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8787 -State Listen;" ^
  "if ($conns) {" ^
  "  $webPids = $conns | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "  foreach ($webProcessId in $webPids) {" ^
  "    if ($webProcessId -and (Get-Process -Id $webProcessId -ErrorAction SilentlyContinue)) {" ^
  "      Write-Host ('Deteniendo proceso web PID ' + $webProcessId);" ^
  "      Stop-Process -Id $webProcessId -Force;" ^
  "    }" ^
  "  }" ^
  "  Start-Sleep -Seconds 3;" ^
  "} else {" ^
  "  Write-Host 'No habia proceso escuchando en 127.0.0.1:8787.';" ^
  "}"

echo.
echo [2/3] Arrancando tarea programada LlangonSuite-Web...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "Start-ScheduledTask -TaskName 'LlangonSuite-Web';" ^
  "Write-Host 'Tarea LlangonSuite-Web iniciada. Esperando healthcheck...';" ^
  "Start-Sleep -Seconds 8;"

echo.
echo [3/3] Comprobando estado...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\windows\status_local_deployment.ps1"

echo.
echo ============================================================
echo Reinicio finalizado.
echo Si Healthcheck web = OK 200, la web esta funcionando.
echo ============================================================
echo.

pause
endlocal