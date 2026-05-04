from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from core.exceptions import ExifToolNotFoundError, ExifToolProcessError
from utils.date_utils import exif_str_to_datetime

logger = logging.getLogger(__name__)

# ExifTool tag priority for "date taken"
_DATE_TAGS = [
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
    "QuickTime:CreateDate",       # MP4/MOV
    "QuickTime:TrackCreateDate",
    "H264:DateTimeOriginal",
]

# Maximum files per ExifTool invocation.  When any file in a batch has a
# fatal error (corrupt JPEG, truncated MP4, wrong-extension text file) ExifTool
# exits with code 1 for the whole group.  Chunking limits the blast radius:
# one bad file can silence at most _CHUNK_SIZE − 1 neighbours instead of the
# entire scan of thousands of files.
_CHUNK_SIZE = 500


class ExifReader:
    def __init__(self, exiftool_path: str = "exiftool") -> None:
        self._exiftool_path = exiftool_path

    def read_date(self, path: Path) -> datetime | None:
        """Read the best available date tag from a single file."""
        results = self.read_batch([path])
        return results.get(path)

    def read_batch(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """
        Read date tags from multiple files in one persistent ExifTool process.

        Returns a mapping of path → datetime (or None if not found / unreadable).

        Resilience strategy
        -------------------
        • Files are processed in chunks of _CHUNK_SIZE (500).  A single corrupt
          file can only discard results for its own chunk, not the full scan.
        • check_execute=False tells pyexiftool not to raise when ExifTool exits
          with code 1 (which happens whenever any file in a chunk has an error).
          ExifTool still writes valid JSON to stdout for every file it *could*
          read; those results are returned normally.
        • The -m flag suppresses minor structural errors (bad IFD pointers,
          OtherImageStart corruption, truncated maker notes) so ExifTool keeps
          reading rather than bailing out on the whole file.
        • If an individual chunk raises despite the above (e.g. malformed JSON
          from a completely garbled ExifTool output), its files silently receive
          None and the remaining chunks continue unaffected.
        """
        if not paths:
            return {}

        try:
            import exiftool  # pyexiftool
        except ImportError as exc:
            raise ExifToolNotFoundError(
                "pyexiftool is not installed. Run: pip install pyexiftool"
            ) from exc

        result: dict[Path, datetime | None] = {p: None for p in paths}
        chunks = [paths[i : i + _CHUNK_SIZE] for i in range(0, len(paths), _CHUNK_SIZE)]

        try:
            with exiftool.ExifToolHelper(
                executable=self._exiftool_path,
                # Don't raise on non-zero exit code — per-file errors write to
                # stderr but ExifTool still outputs valid JSON for good files.
                check_execute=False,
            ) as et:
                for chunk in chunks:
                    self._read_chunk(et, chunk, paths, result)
        except FileNotFoundError as exc:
            raise ExifToolNotFoundError(str(exc)) from exc
        except Exception as exc:
            msg = str(exc).lower()
            if "not found" in msg or "no such file" in msg or "cannot find" in msg:
                raise ExifToolNotFoundError(str(exc)) from exc
            raise ExifToolProcessError(str(exc)) from exc

        return result

    def _read_chunk(
        self,
        et: object,
        chunk: list[Path],
        all_paths: list[Path],
        result: dict[Path, datetime | None],
    ) -> None:
        """Run one ExifTool chunk and merge results into *result*."""
        str_chunk = [str(p) for p in chunk]
        try:
            metadata_list = et.get_tags(  # type: ignore[attr-defined]
                str_chunk,
                tags=_DATE_TAGS,
                params=["-m"],  # ignore minor EXIF structural errors
            )
        except Exception as exc:
            # One chunk failed entirely (e.g. JSON parse error from a
            # completely garbled ExifTool response).  Log and continue so
            # the rest of the scan is unaffected.
            logger.warning(
                "ExifTool chunk read error (%d files will have no EXIF date): %s",
                len(chunk),
                exc,
            )
            return

        for meta in metadata_list:
            source_file = meta.get("SourceFile", "")
            path = Path(source_file)
            if path not in result:
                # ExifTool may normalise separators — try string comparison
                matches = [p for p in all_paths if str(p) == source_file]
                if not matches:
                    continue
                path = matches[0]
            dt = self._extract_date(meta)
            result[path] = dt

    def _extract_date(self, meta: dict) -> datetime | None:
        """Try tags in priority order and return the first valid datetime."""
        for tag in _DATE_TAGS:
            raw = meta.get(tag)
            if raw:
                dt = exif_str_to_datetime(str(raw))
                if dt:
                    return dt
        return None
