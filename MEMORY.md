# Project Memory

## Decisions Made
- 2026-04-27: Chose PyQt6 over CustomTkinter — better for data tables and cross-platform consistency
- 2026-04-27: Write to original files (ExifTool creates _original backups) — user confirmed
- 2026-04-27: Interactive per-file conflict dialog — user confirmed (not silent priority order)
- 2026-04-27: Separated core/ from gui/ entirely — core never imports GUI
- 2026-04-27: Used `from __future__ import annotations` everywhere for Python 3.9 compatibility
- 2026-04-27: Batch ExifTool via pyexiftool ExifToolHelper — avoids N × 0.3s startup cost
- 2026-04-27: ExifTool argfile write strategy (`-execute` between files) — per-file error isolation + single process
- 2026-04-27: DateResolver is a pure function (returns new PhotoFile, never mutates) — easier to test

## What's Been Completed
- [x] Project structure scaffolded (src/, tests/, docs/, scripts/, legacy/)
- [x] pyproject.toml, requirements.txt, setup.sh
- [x] Data models: DateSource, PhotoFile, WriteResult, ScanResult
- [x] Core exceptions hierarchy
- [x] Utility modules: date_utils, path_utils, logging_config
- [x] FileScanner (recursive, case-insensitive, 22 supported extensions)
- [x] FilenameParser (4-layer: camera prefix, ISO, ambiguous, dateutil fallback)
- [x] GoogleJsonReader (photoTakenTime / creationTime, duplicate filename handling)
- [x] DateResolver (5 resolution rules, pure functions, immutable updates)
- [x] ExifToolChecker (startup validation)
- [x] ExifReader (batch via pyexiftool, multiple tag fallbacks)
- [x] ExifWriter (argfile batch write, WriteResult with backup_path)
- [x] ProcessingPipeline (factory, full scan flow, progress callbacks)
- [x] GUI: ResultsTableModel + View + Delegate (sortable, color-coded status)
- [x] GUI: ConflictDialog (multi-file nav, radio options, manual date entry, thumbnail)
- [x] GUI: ScanWorker + WriteWorker (QRunnable, Qt signals, thread-safe)
- [x] GUI: SettingsDialog (ExifTool path, DMY/MDY pref, QSettings persisted)
- [x] GUI: MainWindow (full wiring: scan → table → conflict dialog → write)
- [x] 86 tests — 86 passing (unit + integration, no ExifTool required)

## Known Issues / Blockers
- pyexiftool and PyQt6 not yet pip-installed in this environment (Python 3.9 system install)
- ExifTool binary needs to be installed separately before the app can run
- GUI cannot be visually tested without PyQt6 installed
- tests/integration/test_exif_writer.py not yet written (requires ExifTool + real JPEG fixture)
