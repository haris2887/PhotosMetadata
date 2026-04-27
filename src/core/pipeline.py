from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.exif_reader import ExifReader
from core.filename_parser import FilenameParser
from core.json_reader import GoogleJsonReader
from core.resolver import DateResolver
from core.scanner import FileScanner
from models.photo_file import PhotoFile
from models.scan_result import ScanResult

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    def __init__(
        self,
        scanner: FileScanner,
        exif_reader: ExifReader,
        filename_parser: FilenameParser,
        json_reader: GoogleJsonReader,
        resolver: DateResolver,
    ) -> None:
        self._scanner = scanner
        self._exif_reader = exif_reader
        self._filename_parser = filename_parser
        self._json_reader = json_reader
        self._resolver = resolver

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
        1. Find all supported files
        2. Batch-read EXIF dates
        3. For files missing EXIF: parse filename + look for JSON sidecar
        4. Resolve each file's status
        """
        logger.info("Pipeline starting: %s", root)

        paths = self._scanner.scan(root)
        total = len(paths)
        logger.info("Found %d files to process", total)

        if not paths:
            return ScanResult(root_dir=root, files=[])

        # Step 2: batch EXIF read
        if progress_callback:
            progress_callback(0, total, "Reading EXIF data…")
        exif_dates: dict[Path, datetime | None] = {}
        try:
            exif_dates = self._exif_reader.read_batch(paths)
        except Exception as exc:
            logger.error("EXIF batch read failed: %s", exc)
            # Continue with all dates as None — don't abort the scan

        # Step 3: build PhotoFile objects and enrich missing-EXIF files
        files: list[PhotoFile] = []
        for i, path in enumerate(paths):
            if progress_callback:
                progress_callback(i + 1, total, path.name)

            exif_date = exif_dates.get(path)
            file_type = self._file_type(path)

            file = PhotoFile(
                path=path,
                file_type=file_type,
                exif_date=exif_date,
                status="missing",
                chosen_date=None,
            )

            if exif_date is None:
                # Try to find alternate date sources
                try:
                    file.filename_date = self._filename_parser.parse(path)
                except Exception as exc:
                    logger.debug("Filename parse error for %s: %s", path.name, exc)

                try:
                    json_path = self._json_reader.find_json(path)
                    if json_path:
                        file.json_date = self._json_reader.read_date(json_path)
                except Exception as exc:
                    logger.debug("JSON read error for %s: %s", path.name, exc)
                    file.error = str(exc)

            # Step 4: resolve
            file = self._resolver.resolve(file)
            files.append(file)

        result = ScanResult(root_dir=root, files=files)
        logger.info(
            "Pipeline complete: %d total, %d has_exif, %d missing, "
            "%d auto_queue, %d needs_user",
            result.total, len(result.has_exif), len(result.missing),
            len(result.auto_queue), len(result.needs_user),
        )
        return result

    def _file_type(self, path: Path) -> str:
        video_exts = {
            ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp",
        }
        return "video" if path.suffix.lower() in video_exts else "photo"
