# Architecture

## Overview
PhotosMetadata is a strict two-layer application:

- **Core** (`src/core/`, `src/models/`, `src/utils/`) — pure Python business logic, zero GUI dependencies. Fully testable from the command line or a script with no display.
- **GUI** (`src/gui/`) — PyQt6 presentation layer. Calls into core; never the other way around.

---

## Module Map

```
src/
├── main.py                      Entry point — run with: python src/main.py
│
├── models/
│   ├── photo_file.py            DateSource, PhotoFile, WriteResult dataclasses
│   └── scan_result.py           ScanResult with computed properties
│
├── core/                        ← NO imports from src/gui/ allowed here
│   ├── exceptions.py            ExifToolNotFoundError, ExifToolProcessError,
│   │                            ScanPermissionError, JsonParseError, DateParseError
│   ├── scanner.py               FileScanner — recursive walk, 22 extensions
│   ├── exiftool_checker.py      check_exiftool() — validates binary at startup
│   ├── exif_reader.py           ExifReader.read_batch() — persistent ExifTool process
│   ├── exif_writer.py           ExifWriter.write_batch() — argfile strategy + WriteResult
│   ├── filename_parser.py       FilenameParser — 4-layer regex + dateutil fallback
│   ├── json_reader.py           GoogleJsonReader — Takeout sidecar discovery + parsing
│   ├── resolver.py              DateResolver — 5 pure resolution rules
│   └── pipeline.py              ProcessingPipeline — factory + full scan orchestration
│
├── gui/
│   ├── app.py                   create_app() + main() — QApplication entry point
│   ├── main_window.py           MainWindow (QMainWindow) — top-level controller
│   ├── results_table.py         ResultsTableModel + ResultsTableView + Delegate
│   ├── conflict_dialog.py       ConflictDialog — multi-file Prev/Next navigation
│   ├── scan_worker.py           ScanWorker (QRunnable) — threaded pipeline run
│   ├── write_worker.py          WriteWorker (QRunnable) — threaded batch write
│   └── settings_dialog.py       SettingsDialog — ExifTool path + DMY/MDY, QSettings
│
└── utils/
    ├── date_utils.py            datetime ↔ EXIF string, dates_within_hours
    ├── path_utils.py            get_relative_display_path, safe_stem
    └── logging_config.py        Rotating file logger (5 MB × 3) + stderr WARNING+
```

---

## Data Flow

```
User selects directory
        │
        ▼
FileScanner.scan(root)
        │  list[Path]
        ▼
ExifReader.read_batch(paths)          ← single persistent ExifTool process
        │  dict[Path, datetime|None]
        ▼
Build PhotoFile per path
        │
        ├─ exif_date present?  ──────────────────────────────► status = "has_exif"
        │
        └─ exif_date missing?
               │
               ├─ FilenameParser.parse(path)    → filename_date: DateSource | None
               └─ GoogleJsonReader.find_json()
                    └─ .read_date(json_path)    → json_date:     DateSource | None
                         │
                         ▼
               DateResolver.resolve(file)
                  ├─ 0 sources   → status = "missing"
                  ├─ 1 source    → status = "resolved_single"   (auto-queue)
                  ├─ N sources, agree within 24h → "resolved_single"
                  └─ N sources, conflict > 24h  → "resolved_conflict" (user picks)
        │
        ▼
ScanResult emitted to MainWindow (via Qt signal from ScanWorker)
        │
        ├─► ResultsTableView updated
        │
        └─► ConflictDialog shown for each resolved_conflict file
                  │  user picks a date (or skips)
                  ▼
            chosen_date set on PhotoFile
                  │
                  ▼
            ExifWriter.write_batch()    ← argfile, one -execute block per file
                  │  list[WriteResult]  ← ExifTool creates filename_original backups
                  ▼
            Status bar updated: "N written, M failed"
```

---

## Threading Model

- All scan and write operations run in `QRunnable` workers on `QThreadPool.globalInstance()`
- Cross-thread communication uses **Qt queued signals only** — thread-safe by design
- `ScanResult` is passed as a single completed object to the main thread — no shared mutable state during processing

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| GUI framework | PyQt6 | Best Python-native GUI for sortable data tables |
| ExifTool access | pyexiftool persistent process | Avoids N × 0.3s startup cost per file |
| Write backups | ExifTool default `_original` suffix | Zero data loss risk |
| Threading | `QRunnable` + `QThreadPool` | Qt-native; safe queued signal delivery |
| Resolver | Pure function, `dataclasses.replace` | Immutable — easy to unit test |
| Conflict resolution | Interactive per-file dialog | User wants control, not silent guessing |
| Batch write | ExifTool argfile + `-execute` sentinel | Per-file error isolation in one process |
| Install | `pip install -r requirements.txt` | No build backend — works on all Python installs including Windows Store |
| Compatibility | `from __future__ import annotations` | Runs on Python 3.9+ despite using `X \| Y` syntax |

---

## External Dependency: ExifTool

ExifTool is **not** installed by pip. Users must install it separately:

| Platform | Command |
|---|---|
| macOS | `brew install exiftool` |
| Ubuntu / Debian | `sudo apt-get install libimage-exiftool-perl` |
| Windows | Download from https://exiftool.org, rename to `exiftool.exe`, add to PATH |

The app validates ExifTool is available at startup (`ExifToolChecker`) and shows an error dialog if not found. The path can be overridden in the Settings dialog.
