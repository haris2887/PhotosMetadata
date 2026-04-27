#!/bin/bash
# Setup script for PhotosMetadata development environment
# Can be run from anywhere — it always operates from the project root.

set -e

# ── Always work from the project root (one level above this script) ───────────
cd "$(dirname "$0")/.."

echo "Setting up PhotosMetadata project..."

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MINOR" -ge 9 ] 2>/dev/null; then
            PYTHON="$cmd"
            echo "Found: Python $VERSION"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.9+ not found."
    echo "  macOS:         brew install python@3.12"
    echo "  Ubuntu/Debian: sudo apt-get install python3.12"
    exit 1
fi

# ── Check ExifTool ────────────────────────────────────────────────────────────
if ! command -v exiftool &>/dev/null; then
    echo ""
    echo "WARNING: ExifTool not found. Install it before scanning:"
    echo "  macOS:          brew install exiftool"
    echo "  Ubuntu/Debian:  sudo apt-get install libimage-exiftool-perl"
    echo ""
else
    echo "Found: ExifTool $(exiftool -ver)"
fi

# ── Create virtual environment ────────────────────────────────────────────────
echo "Creating virtual environment (.venv)..."
"$PYTHON" -m venv .venv
source .venv/bin/activate

# ── Install dependencies from requirements.txt ───────────────────────────────
echo "Upgrading pip..."
pip install --upgrade pip --quiet || true   # non-fatal

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete. Activate the environment with:"
echo "  source .venv/bin/activate"
echo ""
echo "Launch the app:"
echo "  python src/main.py"
echo ""
echo "Run tests:"
echo "  pytest tests/unit/                          # no ExifTool needed"
echo "  pytest tests/ -m requires_exiftool          # needs ExifTool installed"
