from __future__ import annotations

from datetime import datetime
from pathlib import Path

from models.photo_file import DateSource, PhotoFile, WriteResult
from models.scan_result import ScanResult


def make_photo(
    status: str = "has_exif",
    exif_date: datetime | None = datetime(2026, 1, 1),
    filename_date: DateSource | None = None,
    json_date: DateSource | None = None,
    error: str | None = None,
) -> PhotoFile:
    return PhotoFile(
        path=Path("/photos/test.jpg"),
        file_type="photo",
        exif_date=exif_date,
        filename_date=filename_date,
        json_date=json_date,
        status=status,  # type: ignore[arg-type]
        chosen_date=exif_date,
        error=error,
    )


class TestPhotoFile:
    def test_alternate_sources_empty(self) -> None:
        f = make_photo()
        assert f.alternate_sources == []

    def test_alternate_sources_filename_only(self) -> None:
        src = DateSource("filename", datetime(2026, 3, 1), "high", "IMG_20260301.jpg")
        f = make_photo(filename_date=src)
        assert f.alternate_sources == [src]

    def test_alternate_sources_both(self) -> None:
        s1 = DateSource("filename", datetime(2026, 3, 1), "high", "IMG_20260301.jpg")
        s2 = DateSource("google_json", datetime(2026, 3, 2), "high", "1234567890")
        f = make_photo(filename_date=s1, json_date=s2)
        assert len(f.alternate_sources) == 2

    def test_display_name(self) -> None:
        f = make_photo()
        assert f.display_name == "test.jpg"


class TestScanResult:
    def _make_result(self) -> ScanResult:
        files = [
            make_photo(status="has_exif"),
            make_photo(status="missing", exif_date=None, error=None),
            make_photo(status="resolved_single", exif_date=None),
            make_photo(status="resolved_conflict", exif_date=None),
            make_photo(status="has_exif", error="some error"),
        ]
        return ScanResult(root_dir=Path("/photos"), files=files)

    def test_total(self) -> None:
        assert self._make_result().total == 5

    def test_has_exif(self) -> None:
        assert len(self._make_result().has_exif) == 2

    def test_missing(self) -> None:
        assert len(self._make_result().missing) == 1

    def test_auto_queue(self) -> None:
        assert len(self._make_result().auto_queue) == 1

    def test_needs_user(self) -> None:
        assert len(self._make_result().needs_user) == 1

    def test_with_errors(self) -> None:
        assert len(self._make_result().with_errors) == 1
