from __future__ import annotations

from datetime import datetime, date
from pathlib import Path

import pytest

from core.exif_reader import ExifReader
from core.exif_writer import ExifWriter


@pytest.mark.requires_exiftool
class TestExifWriterSingleFile:
    def test_write_date_returns_success(self, writable_jpeg: Path) -> None:
        writer = ExifWriter()
        dt = datetime(2026, 3, 28, 14, 22, 0)
        result = writer.write_date(writable_jpeg, dt)
        assert result.success
        assert result.path == writable_jpeg

    def test_write_date_creates_backup(self, writable_jpeg: Path) -> None:
        writer = ExifWriter()
        writer.write_date(writable_jpeg, datetime(2026, 3, 28))
        backup = Path(str(writable_jpeg) + "_original")
        assert backup.exists()

    def test_written_date_readable_back(self, writable_jpeg: Path) -> None:
        writer = ExifWriter()
        reader = ExifReader()
        target_dt = datetime(2023, 10, 25, 14, 30, 22)

        result = writer.write_date(writable_jpeg, target_dt)
        assert result.success

        read_back = reader.read_date(writable_jpeg)
        assert read_back is not None
        assert read_back.date() == target_dt.date()
        assert read_back.hour == target_dt.hour
        assert read_back.minute == target_dt.minute


@pytest.mark.requires_exiftool
class TestExifWriterBatch:
    def test_batch_write_multiple_files(
        self, jpeg_no_exif: Path, tmp_path: Path
    ) -> None:
        import shutil

        files = []
        for i in range(3):
            dest = tmp_path / f"photo_{i}.jpg"
            shutil.copy(jpeg_no_exif, dest)
            files.append(dest)

        tasks = [
            (files[0], datetime(2024, 1, 15)),
            (files[1], datetime(2024, 6, 20)),
            (files[2], datetime(2024, 12, 31)),
        ]
        writer = ExifWriter()
        results = writer.write_batch(tasks)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_batch_progress_callback_called(
        self, writable_jpeg: Path
    ) -> None:
        calls: list[tuple[int, int]] = []
        writer = ExifWriter()
        writer.write_batch(
            [(writable_jpeg, datetime(2026, 1, 1))],
            progress_callback=lambda cur, total: calls.append((cur, total)),
        )
        assert calls == [(1, 1)]

    def test_empty_batch_returns_empty(self) -> None:
        writer = ExifWriter()
        assert writer.write_batch([]) == []


@pytest.mark.requires_exiftool
class TestExifWriterNoBackup:
    def test_no_backup_file_created(self, writable_jpeg: Path) -> None:
        writer = ExifWriter(create_backup=False)
        result = writer.write_date(writable_jpeg, datetime(2026, 3, 28))
        assert result.success
        backup = Path(str(writable_jpeg) + "_original")
        assert not backup.exists()

    def test_no_backup_date_still_written(self, writable_jpeg: Path) -> None:
        writer = ExifWriter(create_backup=False)
        reader = ExifReader()
        writer.write_date(writable_jpeg, datetime(2024, 6, 15))
        read_back = reader.read_date(writable_jpeg)
        assert read_back is not None
        assert read_back.date().year == 2024
        assert read_back.date().month == 6
        assert read_back.date().day == 15
