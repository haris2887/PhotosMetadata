from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class CopyResult:
    source_path: Path
    dest_path: Path
    success: bool
    error: str | None = None


@dataclass
class BackupFile:
    path: Path
    source_root: Path       # which source dir this file came from
    relative_path: Path     # path.relative_to(source_root)
    file_size: int          # bytes

    hash_value: str | None = None
    hash_error: str | None = None

    status: Literal[
        "pending",          # not yet hashed
        "unique",           # not in destination — needs backup
        "backed_up",        # hash found in destination
        "duplicate",        # same hash as another source file
        "error",            # hash or copy failed
    ] = "pending"

    duplicate_of: Path | None = None    # canonical path when status == "duplicate"
    copy_result: CopyResult | None = None

    @property
    def display_name(self) -> str:
        return self.path.name

    @property
    def size_mb(self) -> float:
        return self.file_size / (1024 * 1024)


@dataclass
class BackupResult:
    sources: list[Path]
    destination: Path
    scanned_at: datetime = field(default_factory=datetime.now)
    files: list[BackupFile] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.files)

    @property
    def unique(self) -> list[BackupFile]:
        return [f for f in self.files if f.status == "unique"]

    @property
    def backed_up(self) -> list[BackupFile]:
        return [f for f in self.files if f.status == "backed_up"]

    @property
    def duplicates(self) -> list[BackupFile]:
        return [f for f in self.files if f.status == "duplicate"]

    @property
    def errors(self) -> list[BackupFile]:
        return [f for f in self.files if f.status == "error"]
