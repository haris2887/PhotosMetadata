from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .photo_file import PhotoFile


@dataclass
class ScanResult:
    root_dir: Path
    scanned_at: datetime = field(default_factory=datetime.now)
    files: list[PhotoFile] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.files)

    @property
    def has_exif(self) -> list[PhotoFile]:
        return [f for f in self.files if f.status == "has_exif"]

    @property
    def missing(self) -> list[PhotoFile]:
        return [f for f in self.files if f.status == "missing"]

    @property
    def auto_queue(self) -> list[PhotoFile]:
        return [f for f in self.files if f.status == "resolved_single"]

    @property
    def needs_user(self) -> list[PhotoFile]:
        return [f for f in self.files if f.status == "resolved_conflict"]

    @property
    def with_errors(self) -> list[PhotoFile]:
        return [f for f in self.files if f.error is not None]
