# Project Memory

## Decisions Made
- 2026-04-27: Chose PyQt6 — best Python native GUI for data tables and cross-platform consistency
- 2026-04-27: Write to original files; ExifTool creates `_original` backups automatically (now optional via Settings)
- 2026-04-27: Interactive per-file conflict dialog (not silent priority order) — user confirmed
- 2026-04-27: Core/GUI strict separation — `src/core/` never imports from `src/gui/`
- 2026-04-27: `from __future__ import annotations` everywhere — ensures Python 3.9+ compatibility
- 2026-04-27: Batch ExifTool via pyexiftool `ExifToolHelper` — avoids N × 0.3s startup cost
- 2026-04-27: ExifTool argfile write strategy with `-execute` — per-file error isolation + single process
- 2026-04-27: `DateResolver` is a pure function (returns new `PhotoFile`, never mutates) — easier to test
- 2026-04-27: `pip install -r requirements.txt` in setup scripts (not editable install) — avoids build backend issues on Windows Store Python and older setuptools
- 2026-04-28: Right-click context menu for bulk date resolution added to `MainWindow` — avoids needing to open conflict dialog file-by-file
- 2026-04-28: Backup creation made optional — new `create_backup` checkbox in `SettingsDialog`; default true
- 2026-04-28: Failed-write files moved to `_unwritable/` subfolder — preserves original sub-tree structure
- 2026-04-28: Extension mismatch handled via magic-byte detection in `ExifWriter._fix_extension()` — renames file before write so ExifTool accepts it
- 2026-04-28: OtherImageStart IFD corruption (common 2016 Android bug) handled by binary patch then auto-retry — does not touch primary image
- 2026-04-29: JSON sidecar discovery extended to 4 stages: exact name → alternate ext → prefix match → title match — handles Windows ZIP extraction filename truncation and any Google naming variant
- 2026-04-29: `_DirCache` added to `GoogleJsonReader` — per-directory index built once, cached for scan lifetime; eliminates O(n²) JSON reads; thread-safe via `threading.Lock`
- 2026-04-29: `ProcessingPipeline` enrichment parallelised with `ThreadPoolExecutor(min(32, cpu×2))` — I/O-bound filename parse + JSON lookup scales near-linearly on multi-core systems
- 2026-04-29: JSON sidecars moved alongside images in both `_move_failed_files` and `_move_missing_files` — uses full 4-stage search so renamed/truncated sidecars are found correctly
- 2026-04-29: "Move Missing…" toolbar button added — moves undated files (status=missing) to a user-chosen folder with optional JSON co-move; updates table immediately
- 2026-05-02: `FolderDateParser` added (`src/core/folder_date_parser.py`) — 5-pass extraction of date from folder path components; confidence="medium" for full Y+M+D, "low" for year+month or year-only; folder_date field added to PhotoFile; "Folder Date" column added to results table; medium-confidence folder dates participate in conflict resolution via alternate_sources
- 2026-05-02: dateutil fuzzy parser returns timezone-aware datetimes for filenames containing offset-like suffixes (e.g. `1W4A6781+1.jpg` → `+1` parsed as UTC+1) — fixed by calling `.replace(tzinfo=None)` on the dateutil result in `FilenameParser._dateutil_fallback()`
- 2026-05-02: "Move Selected…" toolbar button added — moves any highlighted rows to a user-chosen folder with optional JSON co-move; identical dialog to "Move Missing…"; removes moved rows from table immediately; enabled after any scan with results

## What's Been Completed
- [x] Project structure scaffolded (`src/`, `tests/`, `docs/`, `scripts/`, `legacy/`)
- [x] `pyproject.toml`, `requirements.txt`, `.gitignore`
- [x] Data models: `DateSource`, `PhotoFile`, `WriteResult`, `ScanResult`
- [x] Custom exception hierarchy (`ExifToolNotFoundError`, `JsonParseError`, etc.)
- [x] Utility modules: `date_utils`, `path_utils`, `logging_config`
- [x] `FileScanner` — recursive walk, 22 supported extensions, case-insensitive
- [x] `FilenameParser` — 4-layer: camera prefixes, ISO-8601, ambiguous DMY/MDY, dateutil fallback; respects `date_pref` setting
- [x] `GoogleJsonReader` — full 4-stage sidecar discovery (exact → alt-ext → prefix → title); `_DirCache` for O(1) repeated lookups; cross-directory search for `_unwritable/` relocations
- [x] `DateResolver` — 5 resolution rules, pure functions, immutable updates via `dataclasses.replace`
- [x] `ExifToolChecker` — startup validation (`exiftool -ver`)
- [x] `ExifReader` — batch read via pyexiftool, multiple tag fallbacks (EXIF, QuickTime, H264)
- [x] `ExifWriter` — argfile batch write, `WriteResult` with `backup_path`; `-m` flag; magic-byte extension fixing; stale-path recovery; OtherImageStart binary patch + retry
- [x] `ProcessingPipeline` — factory method; parallel enrichment via `ThreadPoolExecutor`; results reassembled in original order
- [x] GUI: `ResultsTableModel` + `View` + `Delegate` — sortable, colour-coded status column
- [x] GUI: `ConflictDialog` — multi-file navigation, radio buttons, manual date entry, thumbnail
- [x] GUI: `ScanWorker` + `WriteWorker` — `QRunnable`, Qt signals, thread-safe
- [x] GUI: `SettingsDialog` — ExifTool path, DMY/MDY preference, backup toggle; persisted via `QSettings`
- [x] GUI: `MainWindow` — full wiring: scan → progress bar → table → conflict dialog → write → move-failed flow; "Move Missing…" button
- [x] GUI: `MainWindow` — right-click context menu for bulk date resolution (filename / JSON / folder / earliest / latest)
- [x] GUI: `MainWindow` — "Move Selected…" toolbar button — moves highlighted rows + optional JSON sidecars to chosen folder
- [x] `FolderDateParser` — 5-pass folder path date extraction; `folder_date` field on `PhotoFile`; "Folder Date" column in results table
- [x] Bug fix: `FilenameParser` strips `tzinfo` from `dateutil` result — prevents crash on filenames with `+N` suffixes
- [x] `src/main.py` entry point
- [x] 128 unit tests — all passing
- [x] Cross-platform setup scripts: `setup.sh`, `setup.bat`, `setup.ps1`
- [x] Repo pushed to GitHub: https://github.com/haris2887/PhotosMetadata

## Known Issues / Blockers
- **`_unwritable` and `_undated` folders re-scanned**: if the user scans the same root again, files moved to these folders appear in the next scan. `FileScanner` should exclude them.
- ExifTool must be installed separately (see `scripts/setup.*` for platform instructions)

## Environment Notes
- Development on Windows 11, VS Code + Claude Code extension
- GitHub repo: https://github.com/haris2887/PhotosMetadata (public)
- Run the app: `.\.venv\Scripts\python.exe src/main.py` from project root
- Run tests: `.\.venv\Scripts\python.exe -m pytest tests/unit/` (128 tests, no ExifTool needed)
