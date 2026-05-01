param(
    [switch]$FrontendOnly,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendLogOut = Join-Path $backendDir "backend-server.out.log"
$backendLogErr = Join-Path $backendDir "backend-server.err.log"
$frontendLogOut = Join-Path $frontendDir "frontend-server.out.log"
$frontendLogErr = Join-Path $frontendDir "frontend-server.err.log"

function Test-PortInUse {
    param([int]$Port)

    $matches = netstat -ano | Select-String ":$Port "
    return [bool]$matches
}

function Start-Backend {
    if (Test-PortInUse -Port 8000) {
        Write-Host "Port 8000 is already in use. Backend start skipped."
        return
    }

    Start-Process `
        -FilePath (Join-Path $backendDir ".venv\Scripts\python.exe") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $backendLogOut `
        -RedirectStandardError $backendLogErr | Out-Null

    Write-Host "Backend started: http://127.0.0.1:8000"
    Write-Host "Backend logs: $backendLogOut"
}

function Start-Frontend {
    if (Test-PortInUse -Port 5173) {
        Write-Host "Port 5173 is already in use. Frontend start skipped."
        return
    }

    Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev -- --host 127.0.0.1 --port 5173" `
        -WorkingDirectory $frontendDir `
        -RedirectStandardOutput $frontendLogOut `
        -RedirectStandardError $frontendLogErr | Out-Null

    Write-Host "Frontend started: http://127.0.0.1:5173"
    Write-Host "Frontend logs: $frontendLogOut"
}

if (-not $FrontendOnly) {
    Start-Backend
}

if (-not $BackendOnly) {
    Start-Frontend
}

Write-Host ""
Write-Host "Health check:"
Write-Host "  Backend  -> http://127.0.0.1:8000/api/v1/travel/health"
Write-Host "  Frontend -> http://127.0.0.1:5173"
