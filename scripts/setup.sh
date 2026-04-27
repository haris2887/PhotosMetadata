#!/bin/bash
# Setup script for PhotosMetadata development environment
# Can be run from anywhere — it always operates from the project root.

set -e

# ── Always work from the project root (one level above this script) ───────────
cd "$(dirname "$0")/.."

echo "Setting up PhotosMetadata project..."

# Install ExifTool (required external dependency)
if ! command -v exiftool &> /dev/null; then
    echo "ExifTool not found. Install it for your platform:"
    echo "  macOS:          brew install exiftool"
    echo "  Ubuntu/Debian:  sudo apt-get install libimage-exiftool-perl"
    echo "  Windows:        https://exiftool.org — download and add to PATH"
    echo ""
fi

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev]"

echo ""
echo "Setup complete. Activate the environment with:"
echo "  source .venv/bin/activate"
echo ""
echo "Run tests:"
echo "  pytest tests/unit/                          # no ExifTool needed"
echo "  pytest tests/ -m requires_exiftool          # needs ExifTool installed"
