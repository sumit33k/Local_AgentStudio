#Requires -Version 5.1
# start-local-agentstudio.ps1 — Start Local AgentStudio Pro on Windows
# Binds all services to 127.0.0.1 only. Never exposes ports on 0.0.0.0.
#
# Usage: .\start-local-agentstudio.ps1
# Stop:  Ctrl+C (or close the window)

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir  = Join-Path $ProjectRoot "deepseek-skill-studio\backend"
$FrontendDir = Join-Path $ProjectRoot "deepseek-skill-studio\frontend"

$BackendHost = "127.0.0.1"
$BackendPort = "8000"
$FrontendPort = "3000"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   Local AgentStudio Pro" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Dependency checks (warn only)
# ---------------------------------------------------------------------------
function Test-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Warning "'$Name' not found on PATH. $InstallHint"
        Write-Host ""
    }
}

Test-Command "python"  "Install Python 3.10+ from https://python.org"
Test-Command "node"    "Install Node.js 18 LTS from https://nodejs.org"

# Also accept python3 on Windows if python is not available
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Test-Command "python3" "Install Python 3.10+ from https://python.org"
}

# ---------------------------------------------------------------------------
# Virtual environment check
# ---------------------------------------------------------------------------
$VenvDir = Join-Path $BackendDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Warning "Python virtual environment not found at: $VenvDir"
    Write-Host "  To create it, run:" -ForegroundColor Yellow
    Write-Host "    cd `"$BackendDir`"" -ForegroundColor Yellow
    Write-Host "    python -m venv .venv" -ForegroundColor Yellow
    Write-Host "    .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "    pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host ""
}

# Determine uvicorn path
$UvicornVenv = Join-Path $VenvDir "Scripts\uvicorn.exe"
$UvicornGlobal = Get-Command "uvicorn" -ErrorAction SilentlyContinue

if (Test-Path $UvicornVenv) {
    $Uvicorn = $UvicornVenv
} elseif ($UvicornGlobal) {
    $Uvicorn = $UvicornGlobal.Source
} else {
    Write-Error "uvicorn not found. Please install dependencies:`n  cd `"$BackendDir`"`n  python -m venv .venv`n  .venv\Scripts\Activate.ps1`n  pip install -r requirements.txt"
    exit 1
}

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
$EnvFile = Join-Path $ScriptDir ".env"
if (Test-Path $EnvFile) {
    Write-Host "[INFO] Loading environment from $EnvFile"
    Get-Content $EnvFile | Where-Object { $_ -match "^[^#].*=.*" } | ForEach-Object {
        $parts = $_ -split "=", 2
        $key   = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

# ---------------------------------------------------------------------------
# Start FastAPI backend as a background job
# ---------------------------------------------------------------------------
Write-Host "[INFO] Starting FastAPI backend on ${BackendHost}:${BackendPort} ..."

$BackendJob = Start-Job -ScriptBlock {
    param($Dir, $Uvicorn, $Host, $Port)
    Set-Location $Dir
    & $Uvicorn main:app --host $Host --port $Port --reload
} -ArgumentList $BackendDir, $Uvicorn, $BackendHost, $BackendPort

# ---------------------------------------------------------------------------
# Start Next.js frontend as a background job
# ---------------------------------------------------------------------------
Write-Host "[INFO] Starting Next.js frontend on ${BackendHost}:${FrontendPort} ..."

$FrontendJob = Start-Job -ScriptBlock {
    param($Dir, $Port)
    Set-Location $Dir
    $env:HOST = "127.0.0.1"
    npm run dev -- --port $Port
} -ArgumentList $FrontendDir, $FrontendPort

# ---------------------------------------------------------------------------
# Print ready message
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "----------------------------------------------" -ForegroundColor Green
Write-Host "  Local AgentStudio Pro is starting up." -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:  http://${BackendHost}:${FrontendPort}" -ForegroundColor Green
Write-Host "  API docs:  http://${BackendHost}:${BackendPort}/docs" -ForegroundColor Green
Write-Host "  Health:    http://${BackendHost}:${BackendPort}/health" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# Wait and stream job output; clean up on Ctrl+C
# ---------------------------------------------------------------------------
try {
    while ($true) {
        $BackendJob, $FrontendJob | Receive-Job -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1

        # Exit if both jobs have stopped
        if ($BackendJob.State -ne "Running" -and $FrontendJob.State -ne "Running") {
            Write-Host "[INFO] Both services have stopped."
            break
        }
    }
} finally {
    Write-Host ""
    Write-Host "[INFO] Shutting down Local AgentStudio Pro..." -ForegroundColor Yellow

    foreach ($job in @($BackendJob, $FrontendJob)) {
        if ($null -ne $job) {
            Stop-Job  $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
        }
    }

    Write-Host "[INFO] Stopped. Goodbye." -ForegroundColor Cyan
}
