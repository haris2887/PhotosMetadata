# Project: PhotosMetadata

## What This Project Is
A cross-platform desktop app (Windows / macOS / Linux) that uses ExifTool to scan directories
for photos and videos, identifies files with a missing "Date Taken" (DateTimeOriginal) EXIF tag,
and attempts to recover the correct date from:
1. The filename (various formats: IMG_20260328, 2026-03-28, Screenshot_20260328, etc.)
2. Google Photos Takeout JSON sidecars (photoTakenTime.timestamp), including `.supplemental-metadata.json`

When multiple conflicting date sources exist for a file, the app shows an interactive dialog
asking the user to pick the correct date. Bulk resolution is also available via right-click
context menu. Confirmed dates are written back to the original files via ExifTool (optional
`_original` backups). Files that cannot be written are moved to a `_unwritable/` subfolder.

## Tech Stack
- Language: Python 3.9+ (uses `from __future__ import annotations` for compatibility)
- GUI: PyQt6
- EXIF: pyexiftool (persistent ExifTool process for batch performance)
- Date parsing: python-dateutil (fallback filename parsing)
- Thumbnails: Pillow
- Testing: pytest
- Version Control: Git

## Rules Claude Must Follow
- Never modify files in /legacy/ — that is read-only reference
- Always write tests for new functions
- Use type hints on all Python functions
- Use `from __future__ import annotations` at the top of every Python file
- Ask before making architectural decisions
- Core logic in src/core/ must never import from src/gui/

## Project Structure
```
src/
├── main.py                  ← entry point (run with: python src/main.py)
├── models/                  ← DateSource, PhotoFile, WriteResult, ScanResult
├── core/                    ← all business logic (no GUI imports allowed)
│   ├── scanner.py           ← FileScanner
│   ├── exif_reader.py       ← ExifReader (batch via pyexiftool)
│   ├── exif_writer.py       ← ExifWriter (argfile batch write)
│   ├── exiftool_checker.py  ← check_exiftool() startup validation
│   ├── filename_parser.py   ← FilenameParser (layered regex + dateutil)
│   ├── json_reader.py       ← GoogleJsonReader
│   ├── resolver.py          ← DateResolver (pure functions, no mutation)
│   └── pipeline.py          ← ProcessingPipeline (assembles all core)
├── gui/                     ← PyQt6 windows, widgets, workers
│   ├── main_window.py       ← MainWindow
│   ├── results_table.py     ← ResultsTableModel + View + Delegate
│   ├── conflict_dialog.py   ← ConflictDialog (per-file date resolution)
│   ├── scan_worker.py       ← ScanWorker (QRunnable)
│   ├── write_worker.py      ← WriteWorker (QRunnable)
│   ├── settings_dialog.py   ← SettingsDialog (ExifTool path, DMY/MDY pref, backup toggle)
│   └── app.py               ← QApplication + main()
└── utils/                   ← date_utils, path_utils, logging_config
tests/
├── unit/                    ← no filesystem, no ExifTool required
└── integration/             ← filesystem via tmp_path; ExifTool tests marked requires_exiftool
scripts/
├── setup.sh                 ← macOS / Linux setup
├── setup.bat                ← Windows CMD setup
└── setup.ps1                ← Windows PowerShell setup (recommended)
```

## How to Run
```bash
# 1. Install dependencies (pick your platform script)
bash scripts/setup.sh          # macOS / Linux
scripts\setup.bat              # Windows CMD
.\scripts\setup.ps1            # Windows PowerShell

# 2. Activate virtual environment
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate.bat     # Windows

# 3. Launch the app
python src/main.py

# 4. Run tests
pytest tests/unit/             # no ExifTool needed (78 tests)
pytest tests/                  # full suite, 113 tests (ExifTool must be installed)
```

## Current Status
See MEMORY.md for latest progress.
See TASKS.md for what to work on next.
