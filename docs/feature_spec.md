# Feature Specification

## Implemented Features (v1)

### Scanning
- Recursive directory scan for 22 photo/video extensions (JPEG, PNG, HEIC, RAW, MP4, MOV, etc.)
- Batch EXIF read via a persistent ExifTool process — avoids per-file startup overhead
- **Parallel file enrichment** — filename parsing and JSON sidecar lookup run concurrently
  across `min(32, cpu_count × 2)` threads (e.g. 32 threads on an i9-11900H); near-linear
  speedup on large Takeout archives
- Scan progress bar showing files processed / total and current filename
- Files with an existing `DateTimeOriginal` EXIF tag are shown as "has_exif" and skipped

### Date Recovery
- **Filename parsing** — 4-layer strategy:
  1. Camera prefix patterns (`IMG_YYYYMMDD`, `VID_YYYYMMDD`, `Screenshot_YYYYMMDD`, etc.)
  2. ISO-8601 (`YYYY-MM-DD`)
  3. Ambiguous two-number sequences with DMY / MDY preference (user-configurable)
  4. python-dateutil fallback for non-standard names
- **Google Photos Takeout JSON sidecars** — reads `photoTakenTime` (preferred) or `creationTime`
  - 4-stage sidecar discovery (first match wins):
    1. **Exact name** — `photo.jpg.json`, `photo.jpg.supplemental-metadata.json`, stem variants, `(N)` duplicate cleanup
    2. **Alternate extension** — finds `photo.png.json` when file was renamed to `photo.jpg` by the magic-byte fixer
    3. **Prefix match** — finds `photo.mp4.supplemen.json` and similar Windows ZIP extraction truncations
    4. **Title match** — reads each `.json`'s `"title"` field; recovers any naming variant Google may use
  - **Per-directory index cache** (`_DirCache`) — directory listings and `"title"` fields are
    parsed once per directory per scan; subsequent lookups are O(1); bounded at 512 directories
    (~15 MB max); thread-safe for concurrent access
  - **Cross-directory sidecar search** — if a file was moved to `_unwritable/` without its JSON,
    the original location is also searched automatically
- **Folder path date** — extracts date from the directory path of each file using a 5-pass strategy:
  1. Full date from a single path component (`2020-09-24`, `20200924`, `Birthday Party 2022-03-15`)
  2. Full date assembled from two adjacent components (`2020` + `September-24`, `2020` + `09-24`)
  3. Full date assembled from three adjacent components (`2020` + `September` + `24`, `2020` + `09` + `07`)
  4. Year + month (low confidence) from one or two components (`September 2020`, `2020/January`)
  5. Year only (low confidence) from any component (`Photos from 2020`, `2023`)
  - Full-date results (confidence="medium") participate in conflict resolution alongside filename and JSON dates
  - Year-only and year+month results (confidence="low") are shown in the table but not used by the resolver
- **Date confidence levels** — high / medium / low; shown in the results table

### Conflict Resolution
- When filename date and JSON date disagree by more than 24 hours, file is flagged as "conflict"
- **Per-file ConflictDialog** — shows both candidates, thumbnail preview, manual date entry, Prev/Next navigation
- **Bulk right-click context menu** — apply filename date / JSON date / folder date / earliest / latest to all selected rows at once (skips files that already have EXIF)

### Writing
- Batch write via ExifTool argfile strategy — one `-execute` block per file, single process
- Writes `DateTimeOriginal` and `CreateDate` tags simultaneously
- **Backup creation** — optional (`SettingsDialog` checkbox); when enabled, ExifTool saves `filename_original` before writing
- **Extension mismatch auto-fix** — detects files whose extension doesn't match their magic bytes (e.g. JPEG saved as `.PNG`) and renames before writing
- **Stale path recovery** — if a file was renamed in a previous run, locates the new name automatically
- **Minor EXIF error tolerance** — `-m` flag suppresses bad IFD pointers and other non-fatal structural issues
- **OtherImageStart retry** — files failing with corrupt secondary-image IFD are binary-patched then retried (common in 2016-era Android photos)
- Failed-write files can be moved to a `_unwritable/` subfolder (preserving subfolder structure) via a confirmation dialog; JSON sidecars are moved alongside automatically

### File Management
- **"Move Missing…" toolbar button** — enabled after scan when any files have no recoverable date
  - Opens a dialog showing the count of undated files with:
    - Configurable destination folder (default: `<scan-root>/_undated/`, browseable)
    - Checkbox: "Also move matching JSON sidecar files" (checked by default)
  - Preserves original subfolder structure under the destination
  - Uses the full 4-stage + cross-directory sidecar search to find JSON files correctly
    even when filenames have been corrected or files were previously moved
  - Table and button state update immediately after move
- **"Move Selected…" toolbar button** — enabled after any scan with results
  - Moves whichever rows are highlighted in the table (any status) to a chosen folder
  - Same dialog and options as "Move Missing…": configurable destination + JSON co-move checkbox
  - Preserves relative subfolder structure; removes moved rows from the table immediately

### Settings (persisted via QSettings)
- ExifTool binary path (browse + test button)
- Ambiguous date format preference: Ask / Day-Month-Year (DMY) / Month-Day-Year (MDY)
- Backup creation toggle

### Results Table
- Sortable columns: File, Type, Status, EXIF Date, Filename Date, JSON Date, Folder Date, Chosen Date
- Colour-coded status: green (has_exif), orange (auto-resolved), purple (conflict), red (missing)
- Multi-select with Ctrl/Shift; right-click on any row to open bulk resolve menu

## Out of Scope (v1)
- Exclude `_unwritable/` folder from subsequent scans of the parent directory
- Filter / search bar above results table
- Export summary report (CSV)
- Undo last write
- Dark mode toggle
- Single-file executable packaging (PyInstaller — planned, not yet implemented)
- CI pipeline (planned, not yet implemented)
- Cloud sync, face recognition, AI tagging
