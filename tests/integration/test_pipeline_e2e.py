from __future__ import annotations

"""
End-to-end integration tests that simulate a realistic Google Takeout export.

Directory layout created in tmp_path:
  Photos from 2023/
    IMG_20231025_143022.jpg          ← camera prefix (high confidence filename date)
    IMG_20231025_143022.jpg.json     ← JSON matches filename → auto-resolved
    Screenshot_20231016-212955.jpg   ← screenshot prefix → auto-resolved (no JSON)
    ambiguous_05-03-2023.jpg         ← ambiguous date (DMY/MDY) → conflict or pref-resolved
    no_date_photo.jpg                ← no EXIF, no filename date, has JSON → auto-resolved
    no_date_photo.jpg.json
    totally_unknown.jpg              ← no EXIF, no filename date, no JSON → missing

All tests use a MockExifReader so ExifTool is NOT required.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.exif_reader import ExifReader
from core.filename_parser import FilenameParser
from core.json_reader import GoogleJsonReader
from core.pipeline import ProcessingPipeline
from core.resolver import DateResolver
from core.scanner import FileScanner


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ts(dt: datetime) -> str:
    """Convert a datetime to a Unix timestamp string for JSON sidecars."""
    return str(int(dt.replace(tzinfo=timezone.utc).timestamp()))


def make_pipeline(
    exif_dates: dict[str, datetime | None],
    date_pref: str = "ask",
) -> ProcessingPipeline:
    class MockExifReader(ExifReader):
        def read_batch(self, paths: list[Path]) -> dict[Path, datetime | None]:
            return {p: exif_dates.get(p.name) for p in paths}

    return ProcessingPipeline(
        scanner=FileScanner(),
        exif_reader=MockExifReader(),
        filename_parser=FilenameParser(date_pref=date_pref),
        json_reader=GoogleJsonReader(),
        resolver=DateResolver(),
    )


def _write_json(path: Path, taken_dt: datetime) -> None:
    path.write_text(
        json.dumps({"photoTakenTime": {"timestamp": _ts(taken_dt)}}),
        encoding="utf-8",
    )


# ── Fixture: full Takeout directory ──────────────────────────────────────────

@pytest.fixture()
def takeout_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "Photos from 2023"
    folder.mkdir()

    # 1. Camera prefix filename + matching JSON sidecar
    (folder / "IMG_20231025_143022.jpg").touch()
    _write_json(
        folder / "IMG_20231025_143022.jpg.json",
        datetime(2023, 10, 25, 14, 30, 22),
    )

    # 2. Screenshot prefix — no JSON
    (folder / "Screenshot_20231016-212955.jpg").touch()

    # 3. Ambiguous date filename (05-03-2023 → March 5 DMY or May 3 MDY)
    (folder / "ambiguous_05-03-2023.jpg").touch()

    # 4. No filename date, but has JSON
    (folder / "no_date_photo.jpg").touch()
    _write_json(
        folder / "no_date_photo.jpg.json",
        datetime(2023, 7, 4, 9, 0, 0),
    )

    # 5. Nothing useful at all
    (folder / "totally_unknown.jpg").touch()

    return folder


# ── Tests: default "ask" preference ──────────────────────────────────────────

class TestTakeoutScanDefaultPref:
    def test_file_count(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({f: None for f in [
            "IMG_20231025_143022.jpg",
            "Screenshot_20231016-212955.jpg",
            "ambiguous_05-03-2023.jpg",
            "no_date_photo.jpg",
            "totally_unknown.jpg",
        ]})
        result = pipeline.run(takeout_dir)
        assert result.total == 5

    def test_camera_prefix_auto_resolved(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"IMG_20231025_143022.jpg": None})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "IMG_20231025_143022.jpg")
        # High-confidence filename matches JSON → auto
        assert f.status in ("resolved_single", "resolved_conflict")
        assert f.chosen_date is not None or f.status == "resolved_conflict"

    def test_screenshot_auto_resolved(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"Screenshot_20231016-212955.jpg": None})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "Screenshot_20231016-212955.jpg")
        assert f.status == "resolved_single"
        assert f.chosen_date is not None
        assert f.chosen_date.date().year == 2023
        assert f.chosen_date.date().month == 10
        assert f.chosen_date.date().day == 16

    def test_ambiguous_flagged_as_low_confidence(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"ambiguous_05-03-2023.jpg": None})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "ambiguous_05-03-2023.jpg")
        # "ask" pref: low confidence → resolver treats as needing user input or auto
        assert f.filename_date is not None
        assert f.filename_date.confidence == "low"

    def test_json_only_auto_resolved(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"no_date_photo.jpg": None})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "no_date_photo.jpg")
        assert f.status == "resolved_single"
        assert f.chosen_date is not None
        assert f.chosen_date.date().year == 2023
        assert f.chosen_date.date().month == 7

    def test_totally_unknown_stays_missing(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"totally_unknown.jpg": None})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "totally_unknown.jpg")
        assert f.status == "missing"
        assert f.chosen_date is None

    def test_has_exif_files_not_in_queues(self, takeout_dir: Path) -> None:
        exif_dt = datetime(2023, 5, 1, 10, 0, 0)
        pipeline = make_pipeline({"IMG_20231025_143022.jpg": exif_dt})
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "IMG_20231025_143022.jpg")
        assert f.status == "has_exif"
        assert f.chosen_date == exif_dt


# ── Tests: DMY preference ─────────────────────────────────────────────────────

class TestTakeoutScanDMYPref:
    def test_ambiguous_resolved_as_dmy(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"ambiguous_05-03-2023.jpg": None}, date_pref="dmy")
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "ambiguous_05-03-2023.jpg")
        assert f.filename_date is not None
        assert f.filename_date.confidence == "high"
        # DMY: day=05, month=03 → March 5
        assert f.filename_date.date_value.month == 3
        assert f.filename_date.date_value.day == 5


# ── Tests: MDY preference ─────────────────────────────────────────────────────

class TestTakeoutScanMDYPref:
    def test_ambiguous_resolved_as_mdy(self, takeout_dir: Path) -> None:
        pipeline = make_pipeline({"ambiguous_05-03-2023.jpg": None}, date_pref="mdy")
        result = pipeline.run(takeout_dir)
        f = next(x for x in result.files if x.path.name == "ambiguous_05-03-2023.jpg")
        assert f.filename_date is not None
        assert f.filename_date.confidence == "high"
        # MDY: month=05, day=03 → May 3
        assert f.filename_date.date_value.month == 5
        assert f.filename_date.date_value.day == 3


# ── Tests: progress callback ──────────────────────────────────────────────────

class TestScanProgress:
    def test_progress_callback_fires_for_each_file(self, takeout_dir: Path) -> None:
        calls: list[tuple[int, int]] = []
        pipeline = make_pipeline({})
        pipeline.run(
            takeout_dir,
            progress_callback=lambda cur, total, name: calls.append((cur, total)),
        )
        # Should have one call per file (plus initial 0 call)
        file_calls = [(c, t) for c, t in calls if c > 0]
        assert len(file_calls) == 5
        assert file_calls[-1][0] == file_calls[-1][1]  # last call: current == total

    def test_progress_callback_total_matches_file_count(self, takeout_dir: Path) -> None:
        totals: list[int] = []
        pipeline = make_pipeline({})
        pipeline.run(
            takeout_dir,
            progress_callback=lambda cur, total, name: totals.append(total),
        )
        assert all(t == 5 for t in totals if t > 0)
