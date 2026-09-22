@echo off
setlocal
for %%I in ("%~dp0..\..") do set "LLANGON_REPO_ROOT=%%~fI"
set "LLANGON_PYTHON=%LLANGON_REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%LLANGON_PYTHON%" exit /b 20
pushd "%LLANGON_REPO_ROOT%" >nul
"%LLANGON_PYTHON%" -m webapp.infonalia_webapp.tender_documents.bridge %*
set "LLANGON_EXIT=%ERRORLEVEL%"
popd >nul
exit /b %LLANGON_EXIT%
