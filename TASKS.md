# Task Queue

## 🔴 In Progress
_(nothing currently in progress)_

## 🟡 Ready to Start
- [ ] **Exclude `_unwritable` and `_undated` from scan** — files moved there should not re-appear on the next scan of the parent directory
- [ ] **Filter / search bar** above results table — show only "missing" / "conflict" / "has_exif" rows
- [ ] **Settings: remember last-used directory** between sessions (`QSettings` key `last_directory`)
- [ ] **Export summary report** — CSV of what was changed: path, old date, new date, source

## ⚪ Backlog
- [ ] Undo last write — rename `filename_original` back to `filename` for selected files
- [ ] Dark mode toggle
- [ ] **Single-file packaging (PyInstaller)** — bundle Python + PyQt6 + ExifTool into one `.exe` / macOS binary / Linux binary; see plan at `.claude/plans/how-would-to-combine-immutable-treasure.md`
- [ ] **CI pipeline — GitHub Actions** — `pytest tests/unit/` on every push to `main`; build matrix (Windows / macOS / Linux) on `v*` tag push
- [ ] macOS code signing + notarization (requires Apple Developer account, $99/year)
- [ ] App icon — `.icns` (macOS) + `.ico` (Windows), pass via `icon=` in PyInstaller spec

## ✅ Done
- [x] Photo Backups tab — full 6-stage pipeline (discover → hash sources → detect duplicates → discover dest → hash dest → compare); `BackupWindow`, `BackupTableModel`, `BackupWorker`, `CopyWorker`
- [x] `FileHasher` — stdlib MD5 streaming in 64 KB chunks (no extra dependencies)
- [x] `HashCache` — SQLite cache at `~/.photosmetadata/backup_hashes.db`; skips unchanged files by mtime+size; `clear_all()` for Force Re-Hash
- [x] `MainWindow` refactored to `QTabWidget` (Photo Organiser + Photo Backups tabs)
- [x] SSH source guidance built into BackupWindow (collapsed QGroupBox with WinFSP + SSHFS-Win links)
- [x] `FolderDateParser` — 5-pass date extraction from folder path components (single full date → pair → triple → year+month → year-only)
- [x] `folder_date` field added to `PhotoFile`; "Folder Date" column added to results table (between JSON Date and Chosen Date)
- [x] Medium-confidence folder dates participate in `ConflictDialog` and `DateResolver` via `alternate_sources`
- [x] "Apply Folder Date to Selected" added to right-click bulk-resolve context menu
- [x] Bug fix: `FilenameParser._dateutil_fallback()` now strips `tzinfo` — prevents crash on filenames with `+N` suffixes (e.g. `1W4A6781+1.jpg`)
- [x] "Move Selected…" toolbar button — move any highlighted rows + optional JSON sidecars to a chosen folder
- [x] Project structure scaffolded (`src/`, `tests/`, `docs/`, `scripts/`, `legacy/`)
- [x] `pyproject.toml`, `requirements.txt`, `.gitignore`
- [x] Data models: `DateSource`, `PhotoFile`, `WriteResult`, `ScanResult`
- [x] Custom exception hierarchy (`ExifToolNotFoundError`, `JsonParseError`, etc.)
- [x] Utility modules: `date_utils`, `path_utils`, `logging_config`
- [x] `FileScanner` — recursive walk, 22 supported extensions, case-insensitive
- [x] `FilenameParser` — 4-layer: camera prefixes, ISO-8601, ambiguous DMY/MDY, dateutil fallback
- [x] `GoogleJsonReader` — `photoTakenTime` / `creationTime`, duplicate filename handling
- [x] `GoogleJsonReader` — supplemental-metadata sidecar support (`*.supplemental-metadata.json`)
- [x] `GoogleJsonReader` — alternate extension search (finds `photo.png.json` for renamed `photo.jpg`)
- [x] `GoogleJsonReader` — prefix match fallback (finds `photo.mp4.supplemen.json` — Windows truncation)
- [x] `GoogleJsonReader` — title match fallback (reads `"title"` field from each `.json` in directory)
- [x] `GoogleJsonReader` — `_DirCache` thread-safe per-directory index; eliminates repeated dir reads; O(1) title lookups
- [x] `GoogleJsonReader` — cross-directory search for files moved to `_unwritable/` without their JSON
- [x] `DateResolver` — 5 resolution rules, pure functions, immutable updates via `dataclasses.replace`
- [x] `ExifToolChecker` — startup validation (`exiftool -ver`)
- [x] `ExifReader` — batch read via pyexiftool, multiple tag fallbacks (EXIF, QuickTime, H264)
- [x] `ExifWriter` — argfile batch write, `WriteResult` with `backup_path`
- [x] `ExifWriter` — extension mismatch detection via magic bytes; auto-renames before write
- [x] `ExifWriter` — stale path recovery (finds previously renamed file by trying alternate extensions)
- [x] `ExifWriter` — `-m` flag suppresses minor EXIF structural errors (bad IFD pointers)
- [x] `ExifWriter` — OtherImageStart binary patch + retry: corrupt secondary-image IFD stripped
- [x] `ExifWriter` — JSON sidecar moved alongside image when moving to `_unwritable/`
- [x] `ProcessingPipeline` — factory method, full scan flow with progress callbacks
- [x] `ProcessingPipeline` — parallel enrichment via `ThreadPoolExecutor(min(32, cpu×2))` — near-linear speedup on multi-core systems
- [x] Wire DMY/MDY setting into `FilenameParser` — `date_pref` param passed through `pipeline.create()`
- [x] GUI: `ResultsTableModel` + `View` + `Delegate` — sortable, colour-coded status column
- [x] GUI: `ConflictDialog` — multi-file navigation, radio buttons, manual date entry, thumbnail
- [x] GUI: `ScanWorker` + `WriteWorker` — `QRunnable`, Qt signals, thread-safe
- [x] GUI: `SettingsDialog` — ExifTool path, DMY/MDY preference, backup toggle; persisted via `QSettings`
- [x] GUI: `MainWindow` — scan progress bar (file count + percentage)
- [x] GUI: `MainWindow` — bulk date resolution via right-click context menu (filename / JSON / earliest / latest)
- [x] GUI: `MainWindow` — optional backup creation wired from `SettingsDialog.create_backup()`
- [x] GUI: `MainWindow` — failed-write files moved to `_unwritable/` subfolder on user confirmation; JSON sidecars moved alongside
- [x] GUI: `MainWindow` — "Move Missing…" toolbar button with destination picker and JSON co-move option
- [x] `src/main.py` entry point
- [x] 153 unit tests — all passing
- [x] Cross-platform setup scripts: `setup.sh`, `setup.bat`, `setup.ps1` (UTF-8 BOM fixed)
- [x] Windows path display fixed — `get_relative_display_path` uses `.as_posix()`
- [x] Repo pushed to GitHub: https://github.com/haris2887/PhotosMetadata
