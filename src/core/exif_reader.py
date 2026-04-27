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


class ExifReader:
    def __init__(self, exiftool_path: str = "exiftool") -> None:
        self._exiftool_path = exiftool_path

    def read_date(self, path: Path) -> datetime | None:
        """Read the best available date tag from a single file."""
        results = self.read_batch([path])
        return results.get(path)

    def read_batch(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """
        Read date tags from multiple files in a single ExifTool invocation.
        Returns a mapping of path → datetime (or None if not found / unreadable).
        """
        if not paths:
            return {}

        try:
            import exiftool  # pyexiftool
        except ImportError as exc:
            raise ExifToolNotFoundError(
                "pyexiftool is not installed. Run: pip install pyexiftool"
            ) from exc

        str_paths = [str(p) for p in paths]
        result: dict[Path, datetime | None] = {p: None for p in paths}

        try:
            with exiftool.ExifToolHelper(executable=self._exiftool_path) as et:
                metadata_list = et.get_tags(str_paths, tags=_DATE_TAGS)
        except exiftool.exceptions.ExifToolExecuteError as exc:
            raise ExifToolProcessError(str(exc)) from exc
        except Exception as exc:
            # ExifTool binary not found surfaces as various OS errors
            if "not found" in str(exc).lower() or "no such file" in str(exc).lower():
                raise ExifToolNotFoundError(str(exc)) from exc
            raise ExifToolProcessError(str(exc)) from exc

        for meta in metadata_list:
            source_file = meta.get("SourceFile", "")
            path = Path(source_file)
            if path not in result:
                # ExifTool may normalise the path — try to match
                matches = [p for p in paths if str(p) == source_file]
                if not matches:
                    continue
                path = matches[0]

            dt = self._extract_date(meta)
            result[path] = dt

        return result

    def _extract_date(self, meta: dict) -> datetime | None:
        """Try tags in priority order and return the first valid datetime."""
        for tag in _DATE_TAGS:
            raw = meta.get(tag)
            if raw:
                dt = exif_str_to_datetime(str(raw))
                if dt:
                    return dt
        return None
