# Start FaceVision AI and open it in the browser. Stop with Ctrl+C.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Run scripts\setup.ps1 first."
    exit 1
}
& .\.venv\Scripts\python.exe -m facevision serve --open @args
