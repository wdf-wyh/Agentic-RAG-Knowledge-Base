$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root "frontend"

Write-Host "[1/3] Checking project files..."
if (-not (Test-Path (Join-Path $root ".env"))) {
  Write-Host "No .env found. Copying from .env.example..."
  Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
}

Write-Host "[2/3] Starting backend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; `$env:API_PORT='8002'; python run_api.py"

Write-Host "[3/3] Starting frontend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontend'; npm run dev"

Write-Host ""
Write-Host "Frontend: http://localhost:5175"
Write-Host "Backend Docs: http://localhost:8002/docs"
