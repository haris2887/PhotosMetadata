from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.exceptions import JsonParseError
from models.photo_file import DateSource

logger = logging.getLogger(__name__)

_DUPLICATE_SUFFIX = re.compile(r'\(\d+\)$')

# All media extensions this app handles — used when searching for sidecars of
# renamed files (e.g. a JPEG stored with a .png extension and later corrected,
# leaving the JSON still named *.png.json).
_KNOWN_EXTENSIONS: tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".m4v",
    ".mkv", ".avi", ".tif", ".tiff", ".gif",
)


# ---------------------------------------------------------------------------
# Per-directory JSON index (built once, cached for the lifetime of a scan)
# ---------------------------------------------------------------------------

@dataclass
class _DirIndex:
    """
    Pre-scanned snapshot of every .json file in one directory.

    Built on first access; subsequent lookups are O(1) dict look-ups instead
    of repeated directory listings and file reads.
    """
    files: list[Path] = field(default_factory=list)
    # title value (and its stem) → first matching json path
    by_title: dict[str, Path] = field(default_factory=dict)

    @classmethod
    def build(cls, directory: Path) -> "_DirIndex":
        """
        Scan *directory* once: collect .json paths and parse every file's
        'title' field (Google Takeout metadata) into a lookup dict.
        """
        files: list[Path] = []
        by_title: dict[str, Path] = {}
        try:
            for entry in directory.iterdir():
                if entry.suffix.lower() != ".json":
                    continue
                files.append(entry)
                try:
                    raw = entry.read_text(encoding="utf-8", errors="ignore")
                    data = json.loads(raw)
                    title: str = data.get("title", "")
                    if title:
                        by_title.setdefault(title, entry)
                        stem = Path(title).stem
                        if stem != title:
                            by_title.setdefault(stem, entry)
                except (json.JSONDecodeError, OSError):
                    pass
        except OSError:
            pass
        return cls(files=files, by_title=by_title)


class _DirCache:
    """
    Thread-safe, bounded cache of _DirIndex objects keyed by directory path.

    *maxsize* limits the number of directories held in memory.  With 512
    entries each index is ~10–50 KB, so the cache stays well under 32 MB
    even on the largest Takeout archives — trivial on a 32 GB system and
    safe on machines with 4 GB.

    When the limit is reached the oldest entry is evicted (insertion order).
    """

    def __init__(self, maxsize: int = 512) -> None:
        self._maxsize = maxsize
        self._cache: dict[Path, _DirIndex] = {}
        self._lock = threading.Lock()

    def get(self, directory: Path) -> _DirIndex:
        # Fast path — serve from cache without building
        with self._lock:
            idx = self._cache.get(directory)
            if idx is not None:
                return idx

        # Slow path — build outside the lock so I/O doesn't block other threads.
        # Two threads may build the same index concurrently; last writer wins,
        # which is safe because _DirIndex is read-only after construction.
        idx = _DirIndex.build(directory)

        with self._lock:
            self._cache[directory] = idx
            if len(self._cache) > self._maxsize:
                self._cache.pop(next(iter(self._cache)))

        return idx

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# ---------------------------------------------------------------------------
# Public reader
# ---------------------------------------------------------------------------

class GoogleJsonReader:
    """
    Locates and parses Google Photos Takeout JSON sidecar files.

    A single instance should be reused across all files in one scan so that
    the internal _DirCache is shared — this eliminates repeated directory
    listings and JSON reads when many files share the same parent folder.
    """

    def __init__(self) -> None:
        self._dir_cache = _DirCache()

    def find_json(
        self, photo_path: Path, scan_root: Path | None = None
    ) -> Path | None:
        """
        Locate the Google Photos Takeout JSON sidecar for a photo file.

        Search strategy (fastest first):
        1. Current directory, current filename — standard naming conventions.
        2. Current directory, alternate media extensions — handles files whose
           extension was corrected (photo.png → photo.jpg leaves photo.png.json).
        3. Current directory, prefix match — catches truncated supplemental-
           metadata filenames produced by Windows ZIP extraction near MAX_PATH
           (e.g. photo.mp4.supplemen.json instead of photo.mp4.supplemental-
           metadata.json).
        4. Current directory, title match — reads the 'title' field from each
           .json via the cached _DirIndex; O(1) after the first file in a dir.
        5. If scan_root is provided and the file is under scan_root/_unwritable/,
           repeat steps 1–4 in the original pre-move directory.
        """
        name = photo_path.name
        stem = photo_path.stem
        suffix = photo_path.suffix.lower()
        parent = photo_path.parent

        result = self._search_dir(parent, name, stem, suffix)
        if result:
            return result

        # If the file lives under scan_root/_unwritable/, also check the location
        # it came from before being moved there.
        if scan_root is not None:
            try:
                rel = photo_path.relative_to(scan_root)
                parts = rel.parts
                if len(parts) >= 2 and parts[0] == "_unwritable":
                    original_rel = Path(*parts[1:])
                    original_parent = scan_root / original_rel.parent
                    if original_parent != parent:
                        result = self._search_dir(original_parent, name, stem, suffix)
                        if result:
                            logger.debug(
                                "Found JSON sidecar outside current dir (original location): %s",
                                result,
                            )
                            return result
            except ValueError:
                pass

        return None

    # ------------------------------------------------------------------
    # Internal search helpers
    # ------------------------------------------------------------------

    def _search_dir(
        self, directory: Path, name: str, stem: str, suffix: str
    ) -> Path | None:
        """Run all four search strategies against a single directory."""
        # 1. Exact name candidates
        result = self._first_existing(self._make_candidates(directory, name, stem, suffix))
        if result:
            logger.debug("Found JSON sidecar: %s", result)
            return result

        # 2. Alternate extensions (handles magic-byte-fixed renamed files)
        for ext in _KNOWN_EXTENSIONS:
            if ext == suffix:
                continue
            alt_name = stem + ext
            result = self._first_existing(
                self._make_candidates(directory, alt_name, stem, ext)
            )
            if result:
                logger.debug(
                    "Found JSON sidecar via alternate extension (%s): %s", ext, result
                )
                return result

        # 3. Prefix match — catches truncated supplemental-metadata filenames
        result = self._search_by_prefix(directory, name, stem)
        if result:
            return result

        # 4. Title match — O(1) after first access per directory (cached index)
        result = self._search_by_title(directory, name, stem)
        if result:
            return result

        return None

    def _make_candidates(
        self, parent: Path, name: str, stem: str, suffix: str
    ) -> list[Path]:
        candidates: list[Path] = [
            parent / f"{name}.json",
            parent / f"{name}.supplemental-metadata.json",
            parent / f"{stem}.json",
            parent / f"{stem}.supplemental-metadata.json",
        ]
        clean_stem = _DUPLICATE_SUFFIX.sub("", stem)
        if clean_stem != stem:
            clean_name = clean_stem + suffix
            candidates += [
                parent / f"{clean_name}.json",
                parent / f"{clean_name}.supplemental-metadata.json",
                parent / f"{clean_stem}.json",
                parent / f"{clean_stem}.supplemental-metadata.json",
            ]
        return candidates

    @staticmethod
    def _first_existing(candidates: list[Path]) -> Path | None:
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _search_by_prefix(self, directory: Path, name: str, stem: str) -> Path | None:
        """
        Return the first cached .json whose filename starts with *name* + '.'
        or *stem* + '.'.  Catches any truncation variant of the standard Google
        sidecar suffixes without reading file contents.
        """
        name_prefix = name + "."
        stem_prefix = stem + "."
        idx = self._dir_cache.get(directory)
        for entry in idx.files:
            jname = entry.name
            if jname.startswith(name_prefix) or jname.startswith(stem_prefix):
                logger.debug("Found JSON sidecar by prefix match: %s", entry)
                return entry
        return None

    def _search_by_title(self, directory: Path, name: str, stem: str) -> Path | None:
        """
        Return the .json whose 'title' field matches the photo filename or stem.
        Uses the cached _DirIndex — O(1) dict lookup after the first file in
        each directory triggers the index build.
        """
        idx = self._dir_cache.get(directory)
        result = idx.by_title.get(name) or idx.by_title.get(stem)
        if result:
            logger.debug("Found JSON sidecar by title match: %s", result)
            return result
        return None

    # ------------------------------------------------------------------
    # Date reading
    # ------------------------------------------------------------------

    def read_date(self, json_path: Path) -> DateSource | None:
        """
        Parse a Google Takeout JSON file and return the best DateSource.
        Prefers photoTakenTime (confidence=high) over creationTime (confidence=medium).
        """
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise JsonParseError(f"Cannot read {json_path}: {exc}") from exc

        for key, confidence in [("photoTakenTime", "high"), ("creationTime", "medium")]:
            entry = data.get(key)
            if not entry:
                continue
            ts_str = entry.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = int(ts_str)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
                logger.debug("JSON date (%s): %s → %s", key, json_path.name, dt)
                return DateSource("google_json", dt, confidence, ts_str)  # type: ignore[arg-type]
            except (ValueError, OSError):
                continue

        logger.debug("No usable date found in JSON: %s", json_path)
        return None
