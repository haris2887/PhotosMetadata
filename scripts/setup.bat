@echo off
REM Setup script for PhotosMetadata — Windows (Command Prompt)
REM Can be run from anywhere — it always operates from the project root.
REM
REM For a richer experience with coloured output, use setup.ps1 instead:
REM   powershell -ExecutionPolicy RemoteSigned -File scripts\setup.ps1

REM ── Always work from the project root (one level above this script) ──────────
cd /d "%~dp0.."

echo Setting up PhotosMetadata project...
echo.

REM ── Check Python ────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Download Python 3.12 from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo Found Python %PY_VERSION%

REM ── Check ExifTool ───────────────────────────────────────────────────────────
exiftool -ver >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: ExifTool not found in PATH.
    echo The app will not scan files until ExifTool is installed.
    echo.
    echo Install ExifTool for Windows:
    echo   1. Download the Windows Executable from: https://exiftool.org
    echo   2. Rename "exiftool(-k).exe" to "exiftool.exe"
    echo   3. Place it in a folder on your PATH ^(e.g. C:\Windows or C:\Tools^)
    echo   4. Or set the path in the app Settings dialog
    echo.
) else (
    for /f %%v in ('exiftool -ver') do echo Found ExifTool %%v
)

REM ── Create virtual environment ───────────────────────────────────────────────
echo Creating virtual environment ^(.venv^)...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
)

REM ── Install dependencies ─────────────────────────────────────────────────────
echo Installing dependencies...
.venv\Scripts\pip.exe install --upgrade pip --quiet
.venv\Scripts\pip.exe install -e ".[dev]"
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    exit /b 1
)

echo.
echo Setup complete!
echo.
echo Activate the virtual environment:
echo   .venv\Scripts\activate.bat
echo.
echo Launch the app:
echo   python src\main.py
echo.
echo Run tests:
echo   pytest tests\unit\                    ^(no ExifTool needed^)
echo   pytest tests\ -m requires_exiftool    ^(needs ExifTool installed^)
