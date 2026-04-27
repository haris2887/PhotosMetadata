from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core.exif_reader import ExifReader
from core.filename_parser import FilenameParser
from core.json_reader import GoogleJsonReader
from core.pipeline import ProcessingPipeline
from core.resolver import DateResolver
from core.scanner import FileScanner


def make_pipeline(exif_dates: dict[str, datetime | None]) -> ProcessingPipeline:
    """Build a pipeline with a mocked ExifReader."""

    class MockExifReader(ExifReader):
        def read_batch(self, paths: list[Path]) -> dict[Path, datetime | None]:
            return {p: exif_dates.get(p.name) for p in paths}

    return ProcessingPipeline(
        scanner=FileScanner(),
        exif_reader=MockExifReader(),
        filename_parser=FilenameParser(),
        json_reader=GoogleJsonReader(),
        resolver=DateResolver(),
    )


class TestPipelineHasExif:
    def test_file_with_exif_date(self, tmp_path: Path) -> None:
        photo = tmp_path / "IMG_001.jpg"
        photo.touch()
        dt = datetime(2026, 3, 28)
        pipeline = make_pipeline({"IMG_001.jpg": dt})
        result = pipeline.run(tmp_path)

        assert result.total == 1
        assert len(result.has_exif) == 1
        assert result.files[0].chosen_date == dt
        assert result.files[0].status == "has_exif"


class TestPipelineResolvedFromFilename:
    def test_missing_exif_resolved_from_filename(self, tmp_path: Path) -> None:
        photo = tmp_path / "IMG_20260328_142201.jpg"
        photo.touch()
        pipeline = make_pipeline({"IMG_20260328_142201.jpg": None})
        result = pipeline.run(tmp_path)

        assert result.total == 1
        assert len(result.auto_queue) == 1
        f = result.files[0]
        assert f.status == "resolved_single"
        assert f.chosen_date is not None
        assert f.chosen_date.date().year == 2026
        assert f.chosen_date.date().month == 3
        assert f.chosen_date.date().day == 28


class TestPipelineResolvedFromJson:
    def test_missing_exif_resolved_from_json(self, tmp_path: Path) -> None:
        photo = tmp_path / "no_date.jpg"
        photo.touch()
        # Google Takeout JSON sidecar
        sidecar = tmp_path / "no_date.jpg.json"
        sidecar.write_text(json.dumps({
            "photoTakenTime": {"timestamp": "1711622400"},
        }), encoding="utf-8")

        pipeline = make_pipeline({"no_date.jpg": None})
        result = pipeline.run(tmp_path)

        f = result.files[0]
        assert f.status == "resolved_single"
        assert f.chosen_date is not None


class TestPipelineConflict:
    def test_conflicting_sources_flagged(self, tmp_path: Path) -> None:
        # Filename says March 28, JSON says January 12 — conflict
        photo = tmp_path / "IMG_20260328.jpg"
        photo.touch()
        sidecar = tmp_path / "IMG_20260328.jpg.json"
        sidecar.write_text(json.dumps({
            "photoTakenTime": {"timestamp": "1152572400"},  # 2006-07-10 (far away)
        }), encoding="utf-8")

        pipeline = make_pipeline({"IMG_20260328.jpg": None})
        result = pipeline.run(tmp_path)

        f = result.files[0]
        assert f.status == "resolved_conflict"
        assert f.chosen_date is None


class TestPipelineMissing:
    def test_no_sources_at_all(self, tmp_path: Path) -> None:
        photo = tmp_path / "random_name.jpg"
        photo.touch()
        pipeline = make_pipeline({"random_name.jpg": None})
        result = pipeline.run(tmp_path)

        f = result.files[0]
        assert f.status == "missing"
        assert f.chosen_date is None


class TestPipelineEmpty:
    def test_empty_directory(self, tmp_path: Path) -> None:
        pipeline = make_pipeline({})
        result = pipeline.run(tmp_path)
        assert result.total == 0

    def test_only_unsupported_files(self, tmp_path: Path) -> None:
        (tmp_path / "document.pdf").touch()
        (tmp_path / "data.json").touch()
        pipeline = make_pipeline({})
        result = pipeline.run(tmp_path)
        assert result.total == 0


class TestPipelineFileTypes:
    def test_video_classified_correctly(self, tmp_path: Path) -> None:
        (tmp_path / "VID_20260101.mp4").touch()
        pipeline = make_pipeline({"VID_20260101.mp4": None})
        result = pipeline.run(tmp_path)
        assert result.files[0].file_type == "video"

    def test_photo_classified_correctly(self, tmp_path: Path) -> None:
        (tmp_path / "IMG_20260101.jpg").touch()
        pipeline = make_pipeline({"IMG_20260101.jpg": None})
        result = pipeline.run(tmp_path)
        assert result.files[0].file_type == "photo"
