from __future__ import annotations

import logging
import os
import shutil
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from core.hash_cache import HashCache, _DEFAULT_DB
from core.hasher import FileHasher
from core.scanner import FileScanner
from models.backup_file import BackupFile, BackupResult, CopyResult

logger = logging.getLogger(__name__)

_MAX_WORKERS = min(32, (os.cpu_count() or 1) * 2)

ProgressCB = Callable[[str, int, int, str], None]


class BackupPipeline:
    """
    Six-stage pipeline:
      1. discover_sources  — scan each source root for supported files
      2. hash_sources      — parallel MD5 hash (cache consulted first)
      3. detect_duplicates — group by hash; mark all but first as duplicate
      4. discover_dest     — scan destination root
      5. hash_dest         — parallel MD5 hash of destination files
      6. compare           — non-duplicate sources vs destination hashes
    """

    def __init__(
        self,
        scanner: FileScanner,
        hasher: FileHasher,
        cache: HashCache,
    ) -> None:
        self._scanner = scanner
        self._hasher = hasher
        self._cache = cache

    @classmethod
    def create(cls, db_path: Path = _DEFAULT_DB) -> "BackupPipeline":
        return cls(
            scanner=FileScanner(),
            hasher=FileHasher(),
            cache=HashCache(db_path=db_path),
        )

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(
        self,
        sources: list[Path],
        destination: Path,
        progress_callback: ProgressCB | None = None,
    ) -> BackupResult:
        result = BackupResult(sources=list(sources), destination=destination)

        # ── Stage 1: discover source files ───────────────────────────────
        _cb(progress_callback, "discover_sources", 0, 0, "Scanning source directories…")
        source_paths: list[Path] = []
        source_root_map: dict[Path, Path] = {}
        for root in sources:
            found = self._scanner.scan(root)
            for p in found:
                source_paths.append(p)
                source_root_map[p] = root
        logger.info("Found %d source files across %d source(s)", len(source_paths), len(sources))

        # ── Stage 2: hash source files ───────────────────────────────────
        source_files = self._hash_paths(
            source_paths, source_root_map, "hash_sources", progress_callback
        )
        result.files = source_files

        # ── Stage 3: detect duplicates across sources ─────────────────────
        _cb(progress_callback, "detect_duplicates", 0, len(source_files), "Detecting duplicates…")
        self._detect_duplicates(source_files)
        dup_count = sum(1 for f in source_files if f.status == "duplicate")
        logger.info("Duplicate source files: %d", dup_count)

        # ── Stage 4: discover destination files ──────────────────────────
        _cb(progress_callback, "discover_dest", 0, 0, "Scanning destination…")
        dest_paths = self._scanner.scan(destination)
        logger.info("Found %d destination files", len(dest_paths))

        # ── Stage 5: hash destination files ──────────────────────────────
        dest_files = self._hash_paths(
            dest_paths, {p: destination for p in dest_paths},
            "hash_dest", progress_callback,
        )
        dest_hashes: set[str] = {
            f.hash_value for f in dest_files if f.hash_value is not None
        }

        # ── Stage 6: compare ─────────────────────────────────────────────
        _cb(progress_callback, "compare", 0, len(source_files), "Comparing…")
        unique = backed = 0
        for i, f in enumerate(source_files):
            if f.status == "duplicate" or f.status == "error":
                continue
            if f.hash_value and f.hash_value in dest_hashes:
                f.status = "backed_up"
                backed += 1
            else:
                f.status = "unique"
                unique += 1
            _cb(progress_callback, "compare", i + 1, len(source_files), f.path.name)
        logger.info("Compare complete: %d unique, %d backed_up", unique, backed)

        self._cache.close()
        return result

    def copy_unique(
        self,
        result: BackupResult,
        files: list[BackupFile] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[CopyResult]:
        """
        Copy unique (not-yet-backed-up) files to the destination.

        *files* defaults to result.unique.  Pass a subset to copy only
        selected rows.  Uses shutil.copy2() to preserve mtime/atime/perms.
        """
        targets = files if files is not None else result.unique
        total = len(targets)
        copy_results: list[CopyResult] = []

        for i, bf in enumerate(targets):
            dest_path = result.destination / bf.relative_path
            if progress_callback:
                progress_callback(i, total, bf.path.name)
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(bf.path), str(dest_path))
                cr = CopyResult(
                    source_path=bf.path,
                    dest_path=dest_path,
                    success=True,
                )
                logger.info("Copied %s → %s", bf.path.name, dest_path)
            except Exception as exc:
                cr = CopyResult(
                    source_path=bf.path,
                    dest_path=dest_path,
                    success=False,
                    error=str(exc),
                )
                logger.error("Copy failed for %s: %s", bf.path.name, exc)
            bf.copy_result = cr
            copy_results.append(cr)

        if progress_callback:
            progress_callback(total, total, "")
        return copy_results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _hash_paths(
        self,
        paths: list[Path],
        root_map: dict[Path, Path],
        stage: str,
        progress_callback: ProgressCB | None,
    ) -> list[BackupFile]:
        total = len(paths)
        results_by_path: dict[Path, BackupFile] = {}

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            future_to_path = {
                pool.submit(self._hash_one, p, root_map[p]): p
                for p in paths
            }
            completed = 0
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed += 1
                _cb(progress_callback, stage, completed, total, path.name)
                try:
                    results_by_path[path] = future.result()
                except Exception as exc:
                    logger.error("Hash failed for %s: %s", path.name, exc)
                    source_root = root_map[path]
                    try:
                        rel = path.relative_to(source_root)
                    except ValueError:
                        rel = Path(path.name)
                    results_by_path[path] = BackupFile(
                        path=path,
                        source_root=source_root,
                        relative_path=rel,
                        file_size=_safe_size(path),
                        hash_error=str(exc),
                        status="error",
                    )

        return [results_by_path[p] for p in paths]

    def _hash_one(self, path: Path, source_root: Path) -> BackupFile:
        """Compute (or retrieve from cache) the hash for one file."""
        stat = path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        cached = self._cache.get(path, mtime, size)
        if cached is not None:
            hash_value = cached
        else:
            hash_value = self._hasher.hash_file(path)
            self._cache.put(path, mtime, size, hash_value)

        try:
            rel = path.relative_to(source_root)
        except ValueError:
            rel = Path(path.name)

        return BackupFile(
            path=path,
            source_root=source_root,
            relative_path=rel,
            file_size=size,
            hash_value=hash_value,
            status="pending",
        )

    @staticmethod
    def _detect_duplicates(files: list[BackupFile]) -> None:
        """
        Group source files by hash.  The first occurrence (by list order, i.e.
        discovery order) is the canonical copy; all others become "duplicate".
        """
        seen: dict[str, Path] = {}
        for f in files:
            if f.hash_value is None:
                continue
            if f.hash_value in seen:
                f.status = "duplicate"
                f.duplicate_of = seen[f.hash_value]
            else:
                seen[f.hash_value] = f.path


def _cb(
    cb: ProgressCB | None,
    stage: str,
    current: int,
    total: int,
    name: str,
) -> None:
    if cb:
        cb(stage, current, total, name)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
