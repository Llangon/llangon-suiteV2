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

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\windows\restart_web_manual.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo Reinicio finalizado correctamente.
) else (
  echo Reinicio finalizado con errores. Codigo: %EXIT_CODE%
)
echo.

pause
exit /b %EXIT_CODE%
