from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class DateSource:
    source_type: Literal["exif", "filename", "google_json"]
    date_value: datetime
    confidence: Literal["high", "medium", "low"]
    raw_value: str  # original string shown to user in conflict dialog


@dataclass
class WriteResult:
    path: Path
    success: bool
    backup_path: Path | None = None  # ExifTool creates path_original by default
    error: str | None = None


@dataclass
class PhotoFile:
    path: Path
    file_type: Literal["photo", "video"]

    exif_date: datetime | None = None
    filename_date: DateSource | None = None
    json_date: DateSource | None = None

    status: Literal[
        "has_exif",          # DateTimeOriginal already present
        "missing",           # no date source found
        "resolved_single",   # one source found or all sources agree — auto-queue
        "resolved_conflict", # multiple sources disagree — user must pick
    ] = "missing"

    chosen_date: datetime | None = None  # set by resolver or user decision
    write_result: WriteResult | None = None
    error: str | None = None             # non-fatal scan error

    @property
    def alternate_sources(self) -> list[DateSource]:
        return [s for s in (self.filename_date, self.json_date) if s is not None]

    @property
    def display_name(self) -> str:
        return self.path.name
