@echo off
setlocal
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
cd /d "%~dp0..\backend" || (
  echo [ERROR] Failed to enter backend directory.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Backend venv not found: %CD%\.venv\Scripts\python.exe
  echo [TIP] Install backend dependencies first.
  pause
  exit /b 1
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if "%ERRORLEVEL%"=="0" (
  echo [INFO] Backend is already running.
  echo [INFO] Backend URL: http://127.0.0.1:8000
  echo [INFO] Health URL: http://127.0.0.1:8000/api/v1/travel/health
  pause
  exit /b 0
)

echo [INFO] Starting backend service...
echo [INFO] Backend URL: http://127.0.0.1:8000
echo [INFO] Health URL: http://127.0.0.1:8000/api/v1/travel/health
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "..\runtime-logs\backend.out.log" 2>> "..\runtime-logs\backend.err.log"

set EXIT_CODE=%ERRORLEVEL%
echo [INFO] Backend service exited. Exit code: %EXIT_CODE%
echo [INFO] Recent backend error log:
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command "Get-Content '..\runtime-logs\backend.err.log' -Encoding UTF8 -Tail 30 -ErrorAction SilentlyContinue"
pause
exit /b %EXIT_CODE%
