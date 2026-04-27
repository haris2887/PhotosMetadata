# Project: PhotosMetadata

## What This Project Is
A cross-platform desktop app (Windows / macOS / Linux) that uses ExifTool to scan directories
for photos and videos, identifies files with a missing "Date Taken" (DateTimeOriginal) EXIF tag,
and attempts to recover the correct date from:
1. The filename (various formats: IMG_20260328, 2026-03-28, etc.)
2. Google Photos Takeout JSON sidecars (photoTakenTime.timestamp)

When multiple conflicting date sources exist for a file, the app shows an interactive dialog
asking the user to pick the correct date. Confirmed dates are written back to the original files
via ExifTool (which automatically creates `_original` backups).

## Tech Stack
- Language: Python 3.12 (runs on 3.9+ with `from __future__ import annotations`)
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
├── main.py              ← entry point
├── models/              ← DateSource, PhotoFile, ScanResult dataclasses
├── core/                ← all business logic (no GUI imports)
│   ├── scanner.py       ← FileScanner
│   ├── exif_reader.py   ← ExifReader (batch via pyexiftool)
│   ├── exif_writer.py   ← ExifWriter (argfile batch write)
│   ├── filename_parser.py ← FilenameParser (layered regex + dateutil)
│   ├── json_reader.py   ← GoogleJsonReader
│   ├── resolver.py      ← DateResolver (pure functions)
│   └── pipeline.py      ← ProcessingPipeline (assembles core)
├── gui/                 ← PyQt6 windows, widgets, workers
└── utils/               ← date_utils, path_utils, logging_config
tests/
├── unit/                ← no filesystem, no ExifTool
└── integration/         ← filesystem via tmp_path; ExifTool tests marked requires_exiftool
```

## Current Status
See MEMORY.md for latest progress.
See TASKS.md for what to work on next.
