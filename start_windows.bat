@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been completed in this folder.
  echo Double-click setup_windows.bat first. No training or M5 upload is required.
  pause
  exit /b 1
)
echo Starting SupplySense at http://localhost:8501
echo Keep this terminal open. Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" scripts\launch.py %*
set "SS_EXIT=%ERRORLEVEL%"
if not "%SS_EXIT%"=="0" echo Launch failed. Read the error above or run setup_windows.bat again.
pause
exit /b %SS_EXIT%
