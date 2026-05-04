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
│   │                            • magic-byte extension fixing before each write
│   │                            • stale-path recovery for previously renamed files
│   │                            • -m flag suppresses minor EXIF structural errors
│   │                            • OtherImageStart IFD corruption: auto-retry with -OtherImage=
│   ├── filename_parser.py       FilenameParser(date_pref) — 4-layer regex + dateutil fallback
│   │                            • dateutil result has tzinfo stripped (prevents offset-naive crash)
│   ├── folder_date_parser.py    FolderDateParser — 5-pass date extraction from folder path
│   │                            • Pass 1: full date from single component (YYYY-MM-DD, YYYYMMDD)
│   │                            • Pass 2: full date from two adjacent parts (2020 + September-24)
│   │                            • Pass 3: full date from three adjacent parts (2020 + Sep + 24)
│   │                            • Pass 4: year+month (low confidence) from one or two parts
│   │                            • Pass 5: year only (low confidence) from any component
│   ├── json_reader.py           GoogleJsonReader — Takeout sidecar discovery + parsing
│   │                            • 4-stage search: exact name → alternate ext → prefix → title
│   │                            • _DirIndex: per-directory snapshot (JSON files + title map)
│   │                            • _DirCache: thread-safe bounded cache of _DirIndex (512 dirs)
│   │                            • Cross-directory search for files moved to _unwritable/
│   ├── resolver.py              DateResolver — 5 pure resolution rules
│   └── pipeline.py              ProcessingPipeline.create(date_pref) — assembles all core
│                                • Step 2: single ExifTool batch read (already optimal)
│                                • Step 3: parallel enrichment via ThreadPoolExecutor
│                                  min(32, cpu_count×2) threads — scales to i9/Ryzen 9
│
├── gui/
│   ├── app.py                   create_app() + main() — QApplication entry point
│   ├── main_window.py           MainWindow (QMainWindow) — top-level controller
│   │                            • scan progress bar (file count + %)
│   │                            • right-click bulk resolve (filename / JSON / folder / earliest / latest)
│   │                            • backup toggle wired from SettingsDialog
│   │                            • failed-write files moved to _unwritable/ subfolder
│   │                            • "Move Missing…" button — moves undated files + JSON sidecars
│   │                            • "Move Selected…" button — moves highlighted rows + JSON sidecars
│   ├── results_table.py         ResultsTableModel + ResultsTableView + Delegate
│   ├── conflict_dialog.py       ConflictDialog — multi-file Prev/Next navigation
│   ├── scan_worker.py           ScanWorker (QRunnable) — threaded pipeline run
│   ├── write_worker.py          WriteWorker (QRunnable) — threaded batch write
│   └── settings_dialog.py       SettingsDialog — ExifTool path, DMY/MDY pref,
│                                 backup checkbox; all persisted via QSettings
│
└── utils/
    ├── date_utils.py            datetime ↔ EXIF string, dates_within_hours
    ├── path_utils.py            get_relative_display_path (posix slashes), safe_stem
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
ThreadPoolExecutor (min(32, cpu×2) threads)
        │
        ├─ [thread] path₁ → _enrich_one()
        ├─ [thread] path₂ → _enrich_one()   ← I/O-bound: JSON reads, dir listings
        ├─ [thread] path₃ → _enrich_one()
        │   ...
        │
        │  Each thread calls:
        │    FilenameParser.parse(path)        → filename_date: DateSource | None
        │    GoogleJsonReader.find_json(path)  → json_path (4-stage, cached per dir)
        │      └─ .read_date(json_path)        → json_date: DateSource | None
        │    FolderDateParser.parse(path)      → folder_date: DateSource | None
        │      (confidence="medium" for full Y+M+D; "low" for year+month or year-only)
        │    DateResolver.resolve(file)
        │      ├─ 0 sources   → "missing"
        │      ├─ 1 source    → "resolved_single"   (auto-queue)
        │      ├─ N agree     → "resolved_single"
        │      └─ N conflict  → "resolved_conflict" (user picks)
        │      Note: folder_date only enters alternate_sources when confidence="medium"
        │
        ▼
Reassemble in original scan order → ScanResult
        │
        ▼
ScanResult emitted to MainWindow (via Qt signal from ScanWorker)
        │
        ├─► ResultsTableView updated  (columns: File, Type, Status, EXIF Date,
        │    Filename Date, JSON Date, Folder Date, Chosen Date)
        │   (right-click → bulk resolve: applies filename / JSON / folder / earliest / latest date)
        │
        └─► ConflictDialog shown for each resolved_conflict file
                  │  user picks a date (or skips)
                  ▼
            chosen_date set on PhotoFile
                  │
                  ▼
            ExifWriter.write_batch()
                  │  pre-flight: magic-byte extension fix + stale-path recovery
                  │  first pass: -m flag, one -execute block per file
                  │  retry pass: -OtherImage= for OtherImageStart IFD failures
                  │  list[WriteResult]  ← ExifTool creates filename_original backups (optional)
                  ▼
            Status bar updated: "N written, M failed"
            If M > 0: offer to move failed files to _unwritable/ subfolder
```

---

## GoogleJsonReader: Sidecar Discovery (4-Stage Search)

Each stage is attempted in order; the first match wins. Stages 3–4 use the
shared `_DirCache` so directory listings and JSON reads happen **at most once
per directory per scan**, regardless of thread count.

| Stage | Method | What it finds |
|---|---|---|
| 1 | Exact name candidates | `photo.jpg.json`, `photo.jpg.supplemental-metadata.json`, stem variants, `(N)` duplicate cleanup |
| 2 | Alternate extensions | `photo.png.json` when the file is now `photo.jpg` (magic-byte rename) |
| 3 | Prefix match | `photo.mp4.supplemen.json` — Windows ZIP extraction truncation of long filenames |
| 4 | Title match | Any `.json` in the directory whose `"title"` field equals the photo filename |

**Cross-directory fallback**: if the file lives under `scan_root/_unwritable/`, all four
stages are also run against the corresponding original directory (same relative path without
the `_unwritable` prefix) to find sidecars left behind when only the image was moved.

---

## ExifWriter: Resilience Layers

| Layer | Mechanism | Handles |
|---|---|---|
| Extension mismatch | Magic-byte detection → rename before write | JPEG saved as `.PNG`, `.M4V`, `.HEIC`, etc. |
| Stale scan paths | Existence check → search alternate extensions | File renamed in a prior run; scan result out of date |
| Minor EXIF errors | `-m` flag on all writes | Bad IFD pointers, truncated maker notes |
| OtherImageStart corruption | Binary patch → auto-retry | 2016-era Android JPEG bug (corrupt secondary-image IFD) |

---

## Threading Model

### Scan phase
- `ScanWorker` (QRunnable) runs the pipeline on a Qt thread-pool thread
- Inside the pipeline, `ThreadPoolExecutor` spawns `min(32, cpu_count×2)` worker threads
  for the enrichment phase (filename parse + JSON sidecar lookup)
- Worker count is I/O-bound heuristic: 2× logical cores, capped at 32
  - i9-11900H (8C/16T): 32 threads
  - 4-core / 4-thread laptop: 8 threads
- The `_DirCache` is shared across all enrichment threads; a `threading.Lock`
  guards writes; reads race harmlessly under CPython's GIL
- Results are collected via `as_completed` and reassembled in original discovery
  order before returning `ScanResult`

### Write phase
- `WriteWorker` (QRunnable) calls `ExifWriter.write_batch()` on a single Qt thread-pool thread
- ExifTool handles all parallelism internally via its argfile batch strategy

### Cross-thread communication
- All GUI updates use **Qt queued signals only** — thread-safe by design
- `ScanResult` is passed as a single completed object to the main thread — no shared mutable state after delivery

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| GUI framework | PyQt6 | Best Python-native GUI for sortable data tables |
| ExifTool access | pyexiftool persistent process | Avoids N × 0.3s startup cost per file |
| Write backups | ExifTool default `_original` suffix (optional) | Zero data loss risk; can be disabled in Settings to save disk |
| Scan threading | `QRunnable` outer + `ThreadPoolExecutor` inner | Qt signal safety + I/O-bound parallelism where it matters |
| Enrichment worker count | `min(32, cpu_count × 2)` | I/O-bound work benefits from more threads than cores; cap avoids over-subscription |
| JSON dir cache | `_DirCache` (512 dirs, `threading.Lock`) | Eliminates repeated directory listings; O(1) title lookups; safe under concurrency |
| Resolver | Pure function, `dataclasses.replace` | Immutable — easy to unit test; safe to call from thread pool |
| Conflict resolution | Interactive per-file dialog + bulk right-click | User wants control; bulk menu speeds up large batches |
| Batch write | ExifTool argfile + `-execute` sentinel | Per-file error isolation in one process |
| OtherImageStart retry | Binary patch then second ExifTool pass | Strips only the corrupt secondary-image IFD; primary image untouched |
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
