# MediScribe AI — Server Start Script
# Run this from the project root: .\start.ps1

$env:PYTHONPATH = "src"

# Use python from active virtualenv, or 'py', or 'python'
if (Test-Path ".venv\Scripts\python.exe") {
    $PYTHON = ".venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PYTHON = "py"
} else {
    $PYTHON = "python"
}

Write-Host "Starting MediScribe AI server..." -ForegroundColor Cyan
Write-Host "Python: $PYTHON" -ForegroundColor DarkGray
Write-Host "URL:    http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""

& $PYTHON -m uvicorn mediscribe.main:app --reload --host 127.0.0.1 --port 8000
