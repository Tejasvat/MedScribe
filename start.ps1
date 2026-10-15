# MediScribe AI — Server Start Script
# Run this from the project root: .\start.ps1
# Uses the system Python (where whisperx is installed) instead of the Windows Store Python.

$env:PYTHONPATH = "src"
$PYTHON = "C:\Users\tejas\AppData\Local\Programs\Python\Python312\python.exe"

Write-Host "Starting MediScribe AI server..." -ForegroundColor Cyan
Write-Host "Python: $PYTHON" -ForegroundColor DarkGray
Write-Host "URL:    http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""

& $PYTHON -m uvicorn mediscribe.main:app --reload --host 127.0.0.1 --port 8000
