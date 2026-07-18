@echo off
setlocal
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
cd /d "%~dp0..\frontend" || (
  echo [ERROR] Failed to enter frontend directory.
  pause
  exit /b 1
)

if not exist "node_modules\vite\bin\vite.js" (
  echo [ERROR] Frontend dependencies not found: %CD%\node_modules
  echo [TIP] Run npm ci in the frontend directory first.
  pause
  exit /b 1
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if "%ERRORLEVEL%"=="0" (
  echo [INFO] Frontend is already running.
  echo [INFO] Frontend URL: http://127.0.0.1:5173
  pause
  exit /b 0
)

echo [INFO] Starting frontend service...
echo [INFO] Frontend URL: http://127.0.0.1:5173
"D:\app\nodejs\node.exe" "node_modules\vite\bin\vite.js" --host 127.0.0.1 --port 5173 >> "..\runtime-logs\frontend.out.log" 2>> "..\runtime-logs\frontend.err.log"

set EXIT_CODE=%ERRORLEVEL%
echo [INFO] Frontend service exited. Exit code: %EXIT_CODE%
echo [INFO] Recent frontend error log:
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -Command "Get-Content '..\runtime-logs\frontend.err.log' -Encoding UTF8 -Tail 30 -ErrorAction SilentlyContinue"
pause
exit /b %EXIT_CODE%
