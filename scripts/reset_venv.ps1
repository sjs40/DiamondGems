<#
.SYNOPSIS
Resets local virtual environment and reinstalls DiamondGems with optional extras.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\reset_venv.ps1 -Extras "data"

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\scripts\reset_venv.ps1 -Extras "all"
#>

param(
    [string]$Extras = "data"
)

$ErrorActionPreference = "Stop"

if (Test-Path ".venv") {
    Write-Host "Removing existing .venv..."
    Remove-Item -Recurse -Force ".venv"
}

Write-Host "Creating .venv..."
python -m venv .venv

Write-Host "Installing uv..."
.\.venv\Scripts\python.exe -m pip install -U pip uv

$installTarget = "-e ."
if ($Extras -and $Extras.Trim().Length -gt 0) {
    $installTarget = "-e .[$Extras]"
}

Write-Host "Installing project with uv: $installTarget"
.\.venv\Scripts\uv.exe pip install $installTarget

Write-Host "Running tests..."
.\.venv\Scripts\python.exe -m pytest

Write-Host "Done."
