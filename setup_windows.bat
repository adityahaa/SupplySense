@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if defined SUPPLYSENSE_PYTHON (
  "%SUPPLYSENSE_PYTHON%" scripts\setup.py %*
  goto finished
)
py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>nul
if not errorlevel 1 (
  py -3.12 scripts\setup.py %*
  goto finished
)
py -3.11 -c "import sys; assert sys.version_info[:2] == (3,11)" >nul 2>nul
if not errorlevel 1 (
  py -3.11 scripts\setup.py %*
  goto finished
)
python -c "import sys; assert sys.version_info[:2] in [(3,11),(3,12)]" >nul 2>nul
if not errorlevel 1 (
  python scripts\setup.py %*
  goto finished
)
echo Python 3.11 or 3.12 was not found.
echo Install 64-bit Python from https://www.python.org/downloads/windows/
echo Enable Add Python to PATH, then run this file again.
pause
exit /b 1
:finished
set "SS_EXIT=%ERRORLEVEL%"
if not "%SS_EXIT%"=="0" echo SupplySense setup or launch failed. Read the message above.
if not "%~1"=="--no-launch" pause
exit /b %SS_EXIT%
