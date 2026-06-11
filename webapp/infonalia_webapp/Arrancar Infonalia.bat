@echo off
setlocal

cd /d "%~dp0"

if not defined INFONALIA_HOST set "INFONALIA_HOST=127.0.0.1"
if not defined INFONALIA_PORT set "INFONALIA_PORT=8787"
echo Iniciando Infonalia...
echo.
echo Direccion local:
echo   http://127.0.0.1:%INFONALIA_PORT%
echo.
python app.py

pause
