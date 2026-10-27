# Start DataTalk on Windows: backend + built frontend on one port (8100).
# Requires: .venv with backend/requirements.txt installed, node for the first build.
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$root = $PSScriptRoot

if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Host "[build] frontend/dist missing, building..."
    Push-Location (Join-Path $root "frontend")
    try {
        npm ci --no-audit --no-fund
        npm run build
    } finally {
        Pop-Location
    }
}

Write-Host "[run] http://127.0.0.1:8100"
& (Join-Path $root ".venv\Scripts\python.exe") -m uvicorn app.main:app `
    --host 127.0.0.1 --port 8100 --app-dir (Join-Path $root "backend")