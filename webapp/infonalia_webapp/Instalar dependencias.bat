@echo off
setlocal

cd /d "%~dp0"

echo Instalando dependencias de Infonalia...
echo.

python -m pip install -r requirements.txt

echo.
echo Instalacion finalizada.
pause
