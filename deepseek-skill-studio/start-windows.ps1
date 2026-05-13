$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Checking Ollama..."
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is not installed. Install it from https://ollama.com and rerun this script."
  exit 1
}

try {
  Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get | Out-Null
} catch {
  Write-Host "Starting Ollama service..."
  Start-Process ollama -ArgumentList "serve"
  Start-Sleep -Seconds 3
}

Write-Host "Checking DeepSeek model..."
$models = ollama list
if ($models -notmatch "deepseek-r1") {
  Write-Host "Pulling deepseek-r1:8b. This may take a while."
  ollama pull deepseek-r1:8b
}

Write-Host "Starting backend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn main:app --reload --port 8000"

Write-Host "Starting frontend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm install; npm run dev"

Write-Host "DeepSeek Skill Studio is running at http://localhost:3000"
