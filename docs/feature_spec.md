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

## Photo Backups Tab

A second independent tab for verifying and performing photo backups. It answers:
"Which of my photos are already on the backup drive, which need backing up, and which are
duplicates across my source directories?"

### Sources and Destination
- Users add any number of **source directories** via "Add Source…" (directory picker)
- One **destination directory** (the backup drive or folder) via "Browse…"
- SSH/SFTP locations are supported by mounting them as local drives using
  **WinFSP** + **SSHFS-Win** on Windows; no SSH library is required in the app.
  The UI includes a collapsed "How to add an SSH source" section with links:
  - WinFSP: https://github.com/winfsp/winfsp/releases
  - SSHFS-Win: https://github.com/winfsp/sshfs-win/releases

### 6-Stage Pipeline
The pipeline runs on a background thread (`BackupWorker`) and reports progress through
each stage via Qt signals:

| Stage | Name | What happens |
|---|---|---|
| 1 | `discover_sources` | `FileScanner.scan()` for each source directory; builds list of `BackupFile` |
| 2 | `hash_sources` | Parallel MD5 hashing of all source files; `HashCache` consulted first to skip unchanged files |
| 3 | `detect_duplicates` | Group by hash; first-seen file is canonical ("pending"); all later occurrences → `status="duplicate"` |
| 4 | `discover_dest` | `FileScanner.scan()` on the destination directory |
| 5 | `hash_dest` | Parallel MD5 hashing of all destination files; builds `dict[hash → path]` |
| 6 | `compare` | Non-duplicate source files: hash in dest → `"backed_up"`; otherwise → `"unique"` |

### Hash Cache
- Computed MD5 hashes are persisted to `~/.photosmetadata/backup_hashes.db` (SQLite)
- Cache hit condition: `mtime`, `size`, and hash algorithm all match the stored row
- Files that change on disk are automatically rehashed on the next scan (no manual invalidation needed)
- **"Force Re-Hash"** button clears the entire cache and recomputes all hashes from scratch
- The cache is shared across all sessions and all source/destination directories
- Hashing algorithm: MD5 via Python stdlib `hashlib` (64 KB streaming chunks, ~600 MB/s,
  zero extra dependencies)

### Duplicate Detection
- Two files with the same MD5 hash across any combination of source directories are considered duplicates
- The first file encountered is the canonical copy ("pending" → resolves to "unique" or "backed_up")
- All subsequent files with the same hash → `status="duplicate"` with a `duplicate_of` pointer
- Only the canonical copy is included in the backup operation; duplicates are skipped

### Results Table
- Columns: File, Source Root, Size (MB), Status, Duplicate Of, Hash
- Colour-coded status:
  - Red (`unique`) — not in destination; will be copied by "Backup Unique Files"
  - Green (`backed_up`) — MD5 already present in destination; no action needed
  - Orange (`duplicate`) — same hash as another source file; shows which file is canonical
  - Dark red (`error`) — hash or copy failed

### Backup Copy
- **"Backup Unique Files ▾"** (dropdown tool button):
  - "Backup All Unique" — copies every `status="unique"` file
  - "Backup Selected Rows" — copies only highlighted unique rows
- Uses `shutil.copy2()` — preserves mtime, atime, and permissions
- Preserves original relative folder structure under the destination
  (e.g. `src/2020/vacation/img.jpg` → `dest/2020/vacation/img.jpg`)
- Progress reported per file via `CopyWorker` Qt signals; table updates on completion

## Out of Scope (v1)
- Exclude `_unwritable/` folder from subsequent scans of the parent directory
- Filter / search bar above results table
- Export summary report (CSV)
- Undo last write
- Dark mode toggle
- Single-file executable packaging (PyInstaller — planned, not yet implemented)
- CI pipeline (planned, not yet implemented)
- Cloud sync, face recognition, AI tagging
