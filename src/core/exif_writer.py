from __future__ import annotations

import logging
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from core.exceptions import ExifToolNotFoundError, ExifToolProcessError
from models.photo_file import WriteResult
from utils.date_utils import datetime_to_exif_str

logger = logging.getLogger(__name__)


class ExifWriter:
    def __init__(
        self,
        exiftool_path: str = "exiftool",
        create_backup: bool = True,
    ) -> None:
        self._exiftool_path = exiftool_path
        self._create_backup = create_backup

    def write_date(self, path: Path, date: datetime) -> WriteResult:
        """Write a single file's date. Returns WriteResult."""
        results = self.write_batch([(path, date)])
        return results[0]

    def write_batch(
        self,
        tasks: list[tuple[Path, datetime]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[WriteResult]:
        """
        Write dates to multiple files using a single ExifTool invocation via argfile.
        ExifTool creates <filename>_original backups automatically (no -overwrite_original).
        """
        if not tasks:
            return []

        results: list[WriteResult] = []

        # Build an argfile — one block per file, separated by -execute
        argfile_lines: list[str] = []
        for path, date in tasks:
            date_str = datetime_to_exif_str(date)
            block: list[str] = []
            if not self._create_backup:
                block.append("-overwrite_original")
            block += [
                f"-DateTimeOriginal={date_str}",
                f"-CreateDate={date_str}",
                str(path),
                "-execute",
            ]
            argfile_lines += block

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(argfile_lines) + "\n")
            argfile_path = f.name

        try:
            proc = subprocess.run(
                [self._exiftool_path, "-@", argfile_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise ExifToolNotFoundError(str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise ExifToolProcessError("ExifTool batch write timed out") from exc
        finally:
            Path(argfile_path).unlink(missing_ok=True)

        # Parse ExifTool output — one "N image files updated" line per -execute block
        output_lines = proc.stdout.splitlines()
        error_lines = proc.stderr.splitlines() if proc.stderr else []
        logger.debug("ExifTool write output: %s", output_lines)
        if error_lines:
            logger.warning("ExifTool write stderr: %s", error_lines)

        # Build results per task — ExifTool writes one status line per file
        for i, (path, _date) in enumerate(tasks):
            backup = Path(str(path) + "_original")
            # Find the corresponding output line (1 updated / 0 updated pattern)
            success = self._parse_success(output_lines, i)
            results.append(WriteResult(
                path=path,
                success=success,
                backup_path=backup if backup.exists() else None,
                error=None if success else f"ExifTool reported 0 files updated for {path.name}",
            ))

            if progress_callback:
                progress_callback(i + 1, len(tasks))

        return results

    def _parse_success(self, output_lines: list[str], index: int) -> bool:
        """Find the N-th '1 image files updated' line in ExifTool output."""
        updated_lines = [l for l in output_lines if "image files updated" in l
                         or "image files unchanged" in l]
        if index < len(updated_lines):
            return updated_lines[index].strip().startswith("1 ")
        # If we can't parse, assume success when no error lines
        return True
