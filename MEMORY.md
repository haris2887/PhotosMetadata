# Project Memory

## Decisions Made
- 2026-04-27: Chose PyQt6 — best Python native GUI for data tables and cross-platform consistency
- 2026-04-27: Write to original files; ExifTool creates `_original` backups automatically
- 2026-04-27: Interactive per-file conflict dialog (not silent priority order) — user confirmed
- 2026-04-27: Core/GUI strict separation — `src/core/` never imports from `src/gui/`
- 2026-04-27: `from __future__ import annotations` everywhere — ensures Python 3.9+ compatibility
- 2026-04-27: Batch ExifTool via pyexiftool `ExifToolHelper` — avoids N × 0.3s startup cost
- 2026-04-27: ExifTool argfile write strategy with `-execute` — per-file error isolation + single process
- 2026-04-27: `DateResolver` is a pure function (returns new `PhotoFile`, never mutates) — easier to test
- 2026-04-27: `pip install -r requirements.txt` in setup scripts (not editable install) — avoids build backend issues on Windows Store Python and older setuptools

## What's Been Completed
- [x] Project structure scaffolded (`src/`, `tests/`, `docs/`, `scripts/`, `legacy/`)
- [x] `pyproject.toml`, `requirements.txt`, `.gitignore`
- [x] Data models: `DateSource`, `PhotoFile`, `WriteResult`, `ScanResult`
- [x] Custom exception hierarchy (`ExifToolNotFoundError`, `JsonParseError`, etc.)
- [x] Utility modules: `date_utils`, `path_utils`, `logging_config`
- [x] `FileScanner` — recursive walk, 22 supported extensions, case-insensitive
- [x] `FilenameParser` — 4-layer: camera prefixes, ISO-8601, ambiguous DMY/MDY, dateutil fallback
- [x] `GoogleJsonReader` — `photoTakenTime` / `creationTime`, duplicate filename handling
- [x] `DateResolver` — 5 resolution rules, pure functions, immutable updates via `dataclasses.replace`
- [x] `ExifToolChecker` — startup validation (`exiftool -ver`)
- [x] `ExifReader` — batch read via pyexiftool, multiple tag fallbacks (EXIF, QuickTime, H264)
- [x] `ExifWriter` — argfile batch write, `WriteResult` with `backup_path`
- [x] `ProcessingPipeline` — factory method, full scan flow with progress callbacks
- [x] GUI: `ResultsTableModel` + `View` + `Delegate` — sortable, colour-coded status column
- [x] GUI: `ConflictDialog` — multi-file navigation, radio buttons, manual date entry, thumbnail
- [x] GUI: `ScanWorker` + `WriteWorker` — `QRunnable`, Qt signals, thread-safe
- [x] GUI: `SettingsDialog` — ExifTool path, DMY/MDY preference, persisted via `QSettings`
- [x] GUI: `MainWindow` — full wiring: scan → table → conflict dialog → write
- [x] `src/main.py` entry point
- [x] 86 unit + integration tests — all passing
- [x] Cross-platform setup scripts: `setup.sh`, `setup.bat`, `setup.ps1`
- [x] Repo pushed to GitHub: https://github.com/haris2887/PhotosMetadata

## Known Issues / Blockers
- `pyexiftool` and `PyQt6` not installed in the macOS dev environment (no Python 3.12 venv set up yet) — GUI untested visually
- `tests/integration/test_exif_writer.py` not yet written — needs a real JPEG fixture and ExifTool installed
- `tests/fixtures/` is empty — add a small JPEG (with and without EXIF) for integration tests
- DMY/MDY Settings preference is saved but not yet wired into `FilenameParser` — always defaults to first valid parse
- ExifTool must be installed separately (see `scripts/setup.*` for platform instructions)

## Environment Notes
- Development is continuing on Windows with VS Code + Claude Code extension
- GitHub repo: https://github.com/haris2887/PhotosMetadata (public)
- Python installed from Windows Store — use `python src/main.py` to launch, not the package entry point
