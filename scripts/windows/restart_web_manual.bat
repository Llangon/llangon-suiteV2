@echo off
setlocal

REM ============================================================
REM Reinicio manual de Llangon Suite Web
REM Ubicacion recomendada:
REM scripts\windows\restart_web_manual.bat
REM ============================================================

set "PROJECT_ROOT=%~dp0..\.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
  set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
)

echo.
echo ============================================================
echo Reiniciando Llangon Suite Web
echo Proyecto: %PROJECT_ROOT%
echo ============================================================
echo.

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\windows\restart_web_manual.ps1"
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
