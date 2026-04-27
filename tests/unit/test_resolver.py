from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.resolver import DateResolver
from models.photo_file import DateSource, PhotoFile


def make_source(
    source_type: str = "filename",
    dt: datetime = datetime(2026, 3, 28),
    confidence: str = "high",
    raw: str = "IMG_20260328.jpg",
) -> DateSource:
    return DateSource(source_type, dt, confidence, raw)  # type: ignore[arg-type]


def make_file(
    exif_date: datetime | None = None,
    filename_date: DateSource | None = None,
    json_date: DateSource | None = None,
) -> PhotoFile:
    return PhotoFile(
        path=Path("/photos/test.jpg"),
        file_type="photo",
        exif_date=exif_date,
        filename_date=filename_date,
        json_date=json_date,
        status="missing",
        chosen_date=None,
    )


@pytest.fixture
def resolver() -> DateResolver:
    return DateResolver()


class TestResolverRules:
    def test_rule1_has_exif(self, resolver: DateResolver) -> None:
        dt = datetime(2026, 3, 28)
        result = resolver.resolve(make_file(exif_date=dt))
        assert result.status == "has_exif"
        assert result.chosen_date == dt

    def test_rule2_no_sources(self, resolver: DateResolver) -> None:
        result = resolver.resolve(make_file())
        assert result.status == "missing"
        assert result.chosen_date is None

    def test_rule3_single_source(self, resolver: DateResolver) -> None:
        src = make_source(dt=datetime(2026, 3, 28))
        result = resolver.resolve(make_file(filename_date=src))
        assert result.status == "resolved_single"
        assert result.chosen_date == datetime(2026, 3, 28)

    def test_rule4_agreeing_sources(self, resolver: DateResolver) -> None:
        src1 = make_source("filename",    datetime(2026, 3, 28, 0,  0, 0), "high")
        src2 = make_source("google_json", datetime(2026, 3, 28, 12, 0, 0), "high")
        result = resolver.resolve(make_file(filename_date=src1, json_date=src2))
        assert result.status == "resolved_single"

    def test_rule5_conflicting_sources(self, resolver: DateResolver) -> None:
        src1 = make_source("filename",    datetime(2026, 3, 28))
        src2 = make_source("google_json", datetime(2026, 1, 12))
        result = resolver.resolve(make_file(filename_date=src1, json_date=src2))
        assert result.status == "resolved_conflict"
        assert result.chosen_date is None

    def test_exif_takes_priority_over_alternates(self, resolver: DateResolver) -> None:
        exif_dt = datetime(2026, 3, 28)
        src = make_source(dt=datetime(2020, 1, 1))
        result = resolver.resolve(make_file(exif_date=exif_dt, filename_date=src))
        assert result.status == "has_exif"
        assert result.chosen_date == exif_dt

    def test_highest_confidence_chosen_when_agreeing(self, resolver: DateResolver) -> None:
        src_low  = make_source("filename",    datetime(2026, 3, 28), "low")
        src_high = make_source("google_json", datetime(2026, 3, 28, 6, 0, 0), "high")
        result = resolver.resolve(make_file(filename_date=src_low, json_date=src_high))
        assert result.status == "resolved_single"
        assert result.chosen_date == src_high.date_value

    def test_does_not_mutate_input(self, resolver: DateResolver) -> None:
        original = make_file()
        resolver.resolve(original)
        assert original.status == "missing"
        assert original.chosen_date is None
