# Setup script for PhotosMetadata — Windows (PowerShell)
# Run from the project root:  .\scripts\setup.ps1
#
# Requirements:
#   - PowerShell 5.1+ (built into Windows 10/11) or PowerShell 7+
#   - Python 3.12  https://www.python.org/downloads/
#   - ExifTool     https://exiftool.org  (see instructions below)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Setting up PhotosMetadata project..." -ForegroundColor Cyan

# ── Check Python ─────────────────────────────────────────────────────────────
$pythonCmd = $null
foreach ($cmd in @("python3.12", "python3", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $version = & $cmd --version 2>&1
        if ($version -match "3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 9) {
                $pythonCmd = $cmd
                Write-Host "Found: $version" -ForegroundColor Green
                break
            }
        }
    }
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "ERROR: Python 3.9+ not found." -ForegroundColor Red
    Write-Host "Download Python 3.12 from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

# ── Check ExifTool ────────────────────────────────────────────────────────────
if (-not (Get-Command "exiftool" -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "WARNING: ExifTool not found in PATH." -ForegroundColor Yellow
    Write-Host "The app will not be able to scan files until ExifTool is installed."
    Write-Host ""
    Write-Host "Install ExifTool for Windows:"
    Write-Host "  1. Download the Windows Executable from: https://exiftool.org"
    Write-Host "  2. Rename 'exiftool(-k).exe' to 'exiftool.exe'"
    Write-Host "  3. Place it in a folder on your PATH (e.g. C:\Windows or C:\Tools)"
    Write-Host "  4. Or set the ExifTool path in the app's Settings dialog"
    Write-Host ""
} else {
    $etVersion = & exiftool -ver 2>&1
    Write-Host "Found: ExifTool $etVersion" -ForegroundColor Green
}

# ── Create virtual environment ────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating virtual environment (.venv)..."
& $pythonCmd -m venv .venv

# ── Activate and install dependencies ────────────────────────────────────────
Write-Host "Installing dependencies..."
$pip = ".\.venv\Scripts\pip.exe"
& $pip install --upgrade pip --quiet
& $pip install -e ".[dev]"

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Activate the virtual environment:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "If you see an execution policy error, run this first (once):"
Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
Write-Host ""
Write-Host "Launch the app:"
Write-Host "  python src\main.py"
Write-Host ""
Write-Host "Run tests:"
Write-Host "  pytest tests\unit\                    # no ExifTool needed"
Write-Host "  pytest tests\ -m requires_exiftool    # needs ExifTool installed"
