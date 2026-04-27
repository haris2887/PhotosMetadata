# Architecture

## Overview
PhotosMetadata is structured as a strict two-layer application:
- **Core** (`src/core/`, `src/models/`, `src/utils/`) — pure Python business logic with zero GUI dependencies
- **GUI** (`src/gui/`) — PyQt6 presentation layer that calls into core

This separation means the entire back-end can be driven from a script or test without a display.

## Module Map

```
src/
├── main.py
├── models/
│   ├── photo_file.py     DateSource, PhotoFile, WriteResult
│   └── scan_result.py    ScanResult
├── core/
│   ├── exceptions.py     ExifToolNotFoundError, ExifToolProcessError, …
│   ├── scanner.py        FileScanner — recursive directory walk
│   ├── exiftool_checker.py  check_exiftool() — startup validation
│   ├── exif_reader.py    ExifReader.read_batch() — persistent ExifTool process
│   ├── exif_writer.py    ExifWriter.write_batch() — argfile strategy
│   ├── filename_parser.py   FilenameParser — 4-layer regex + dateutil
│   ├── json_reader.py    GoogleJsonReader — Takeout JSON sidecars
│   ├── resolver.py       DateResolver — pure resolution rules
│   └── pipeline.py       ProcessingPipeline — assembles all core components
├── gui/
│   ├── app.py            QApplication + main() entry point
│   ├── main_window.py    MainWindow (QMainWindow) — top-level controller
│   ├── results_table.py  ResultsTableModel + View + Delegate
│   ├── conflict_dialog.py   ConflictDialog — per-file date conflict resolution
│   ├── scan_worker.py    ScanWorker (QRunnable) — threaded pipeline
│   ├── write_worker.py   WriteWorker (QRunnable) — threaded writes
│   └── settings_dialog.py   SettingsDialog — ExifTool path, DMY/MDY pref
└── utils/
    ├── date_utils.py     datetime ↔ EXIF string, tolerance checks
    ├── path_utils.py     display paths, safe_stem
    └── logging_config.py rotating file + stderr logger
```

## Data Flow

```
User selects directory
        │
        ▼
FileScanner.scan(root)          → list[Path]
        │
        ▼
ExifReader.read_batch(paths)    → dict[Path, datetime|None]
        │
        ▼
For each file missing EXIF:
  FilenameParser.parse(path)    → DateSource | None
  GoogleJsonReader.read_date()  → DateSource | None
        │
        ▼
DateResolver.resolve(file)      → PhotoFile (status + chosen_date set)
        │
        ▼
ScanResult emitted to MainWindow
        │
        ├── ResultsTableView updated
        └── ConflictDialog shown for resolved_conflict files
                │
                ▼
        User picks date per file
                │
                ▼
        ExifWriter.write_batch()  → WriteResult[] (with _original backups)
```

## Threading Model
- Scan and write operations run in `QRunnable` workers on `QThreadPool`
- All cross-thread communication uses Qt signals (queued connections — thread-safe)
- Completed `ScanResult` is passed as a single signal payload — no shared mutable state

## Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| GUI framework | PyQt6 | Best Python native GUI for data tables |
| ExifTool access | pyexiftool persistent process | Avoids N × 0.3s startup cost |
| Write backups | ExifTool default `_original` | Safety first |
| Threading | QRunnable + QThreadPool | Qt-native, safe signal delivery |
| Resolver | Pure function, returns new object | Easier to test, no hidden mutation |
| Conflict resolution | Interactive per-file dialog | User wants control, not silent priority |
| Batch write | ExifTool argfile with -execute | Per-file error isolation + single process |
