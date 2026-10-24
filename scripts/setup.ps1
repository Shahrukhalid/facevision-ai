# FaceVision AI setup for Windows 10/11 (PowerShell).
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = $null
foreach ($v in @("3.12", "3.13", "3.11", "3.10")) {
    try { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $python = @("py", "-$v"); break } } catch {}
}
if (-not $python) {
    Write-Host "Python 3.10-3.13 is required. Install Python 3.12 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH') and run this again."
    exit 1
}
Write-Host "Using Python $($python[1])"

& $python[0] $python[1] -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock -q
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps -q

if (Test-Path facevision\web\index.html) {
    Write-Host "Web app already built."
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Building the web app..."
    Push-Location frontend
    npm ci --no-audit --no-fund
    npm run build
    Pop-Location
} else {
    Write-Host "Node.js was not found, so the web app was not built. Install Node.js 20+ from https://nodejs.org and run this again."
}

if ($env:FV_SKIP_MODELS -ne "1") {
    Write-Host "Downloading the default models (about 80 MB, verified with SHA-256)..."
    & .\.venv\Scripts\python.exe -m facevision models install --defaults
}
Write-Host ""
Write-Host "Done. Start FaceVision AI with: powershell -ExecutionPolicy Bypass -File scripts\start.ps1"
