from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from core.exif_reader import ExifReader
from core.filename_parser import FilenameParser
from core.folder_date_parser import FolderDateParser
from core.json_reader import GoogleJsonReader
from core.resolver import DateResolver
from core.scanner import FileScanner
from models.photo_file import PhotoFile
from models.scan_result import ScanResult

logger = logging.getLogger(__name__)

# I/O-bound work saturates I/O queues long before it saturates CPU cores, so
# we use 2× logical-CPU count.  The cap of 32 prevents over-subscription on
# machines with very high core counts where disk I/O would be the bottleneck.
_MAX_WORKERS = min(32, (os.cpu_count() or 1) * 2)


class ProcessingPipeline:
    def __init__(
        self,
        scanner: FileScanner,
        exif_reader: ExifReader,
        filename_parser: FilenameParser,
        json_reader: GoogleJsonReader,
        resolver: DateResolver,
        folder_date_parser: FolderDateParser | None = None,
    ) -> None:
        self._scanner = scanner
        self._exif_reader = exif_reader
        self._filename_parser = filename_parser
        self._json_reader = json_reader
        self._resolver = resolver
        self._folder_date_parser = folder_date_parser or FolderDateParser()

    @classmethod
    def create(
        cls,
        exiftool_path: str = "exiftool",
        date_pref: str = "ask",
    ) -> "ProcessingPipeline":
        """Factory that wires up a default pipeline."""
        return cls(
            scanner=FileScanner(),
            exif_reader=ExifReader(exiftool_path=exiftool_path),
            filename_parser=FilenameParser(date_pref=date_pref),
            json_reader=GoogleJsonReader(),
            resolver=DateResolver(),
        )

    def run(
        self,
        root: Path,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> ScanResult:
        """
        Full scan pipeline:
        1. Discover all supported files under *root*.
        2. Batch-read EXIF dates (single ExifTool process — already optimal).
        3. Enrich files missing EXIF in parallel: filename parse + JSON sidecar
           lookup run concurrently across _MAX_WORKERS threads.
        4. Reassemble results in original discovery order.
        """
        logger.info("Pipeline starting: %s", root)

        paths = self._scanner.scan(root)
        total = len(paths)
        logger.info("Found %d files to process", total)

        if not paths:
            return ScanResult(root_dir=root, files=[])

        # Step 2: batch EXIF read — single persistent ExifTool process
        if progress_callback:
            progress_callback(0, total, "Reading EXIF data…")
        exif_dates: dict[Path, datetime | None] = {}
        try:
            exif_dates = self._exif_reader.read_batch(paths)
        except Exception as exc:
            logger.error("EXIF batch read failed: %s", exc)
            # Continue with all dates as None — don't abort the scan

        # Step 3: parallel enrichment
        # Each file's filename parse + JSON sidecar lookup is independent and
        # I/O-bound, so ThreadPoolExecutor scales near-linearly up to _MAX_WORKERS.
        # The shared GoogleJsonReader caches per-directory JSON indexes so that
        # re-listing the same directory is done at most once across all threads.
        logger.info(
            "Enriching %d files using %d worker threads", total, _MAX_WORKERS
        )
        results_by_path: dict[Path, PhotoFile] = {}

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            future_to_path = {
                pool.submit(self._enrich_one, path, exif_dates.get(path), root): path
                for path in paths
            }
            completed = 0
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, path.name)
                try:
                    results_by_path[path] = future.result()
                except Exception as exc:
                    logger.error("Enrichment failed for %s: %s", path.name, exc)
                    # Fallback: unresolved file with no date sources
                    results_by_path[path] = self._resolver.resolve(
                        PhotoFile(
                            path=path,
                            file_type=self._file_type(path),
                            exif_date=exif_dates.get(path),
                            status="missing",
                            chosen_date=None,
                        )
                    )

        # Step 4: reassemble in original discovery order so the table is stable
        files = [results_by_path[p] for p in paths]

        result = ScanResult(root_dir=root, files=files)
        logger.info(
            "Pipeline complete: %d total, %d has_exif, %d missing, "
            "%d auto_queue, %d needs_user",
            result.total, len(result.has_exif), len(result.missing),
            len(result.auto_queue), len(result.needs_user),
        )
        return result

    # ------------------------------------------------------------------
    # Per-file enrichment — called from thread pool, must be thread-safe
    # ------------------------------------------------------------------

    def _enrich_one(
        self, path: Path, exif_date: datetime | None, root: Path
    ) -> PhotoFile:
        """
        Build and fully enrich a single PhotoFile.

        Thread-safe: FilenameParser, GoogleJsonReader (with its _DirCache),
        DateResolver, and ExifTool reads are all safe to call concurrently.
        """
        file = PhotoFile(
            path=path,
            file_type=self._file_type(path),
            exif_date=exif_date,
            status="missing",
            chosen_date=None,
        )

        if exif_date is None:
            try:
                file.filename_date = self._filename_parser.parse(path)
            except Exception as exc:
                logger.debug("Filename parse error for %s: %s", path.name, exc)

            try:
                json_path = self._json_reader.find_json(path, scan_root=root)
                if json_path:
                    file.json_date = self._json_reader.read_date(json_path)
            except Exception as exc:
                logger.debug("JSON read error for %s: %s", path.name, exc)
                file.error = str(exc)

            try:
                file.folder_date = self._folder_date_parser.parse(path)
            except Exception as exc:
                logger.debug("Folder date parse error for %s: %s", path.name, exc)

        return self._resolver.resolve(file)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _file_type(self, path: Path) -> str:
        video_exts = {
            ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp",
        }
        return "video" if path.suffix.lower() in video_exts else "photo"
