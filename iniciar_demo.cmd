@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo Falta .venv. Sigue Primera instalacion en docs\WINDOWS.md.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" gestionar_demo_windows.py iniciar
set "DEMO_EXIT=%ERRORLEVEL%"
popd
exit /b %DEMO_EXIT%
