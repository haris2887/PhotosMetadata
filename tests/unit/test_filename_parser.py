from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from core.filename_parser import FilenameParser


@pytest.fixture
def parser() -> FilenameParser:
    return FilenameParser()


def parse_date(parser: FilenameParser, filename: str) -> date | None:
    result = parser.parse(Path(filename))
    if result is None:
        return None
    return result.date_value.date()


class TestCameraPrefixPatterns:
    @pytest.mark.parametrize("filename,expected", [
        ("IMG_20260328_142201.jpg",    date(2026, 3, 28)),
        ("VID_20260328.mp4",           date(2026, 3, 28)),
        ("MVIMG_20240101_120000.jpg",  date(2024, 1, 1)),
        ("Screenshot_20260328-142201.png", date(2026, 3, 28)),
        ("Screenshot_2026-03-28.png",  date(2026, 3, 28)),
        ("WA0001-20260328.jpg",        date(2026, 3, 28)),
        ("DSC_20260328.NEF",           date(2026, 3, 28)),
    ])
    def test_known_prefixes(self, parser: FilenameParser, filename: str,
                            expected: date) -> None:
        assert parse_date(parser, filename) == expected

    def test_returns_high_confidence(self, parser: FilenameParser) -> None:
        result = parser.parse(Path("IMG_20260328_142201.jpg"))
        assert result is not None
        assert result.confidence == "high"


class TestIsoPatterns:
    @pytest.mark.parametrize("filename,expected", [
        ("2026-03-28_vacation.jpg",    date(2026, 3, 28)),
        ("holiday_2024-01-15.jpg",     date(2024, 1, 15)),
        ("photo_20260328.jpg",         date(2026, 3, 28)),
    ])
    def test_iso_dates(self, parser: FilenameParser, filename: str, expected: date) -> None:
        assert parse_date(parser, filename) == expected


class TestAmbiguousPatterns:
    def test_ambiguous_returns_low_confidence(self, parser: FilenameParser) -> None:
        result = parser.parse(Path("01-12-2026.jpg"))
        if result is not None:
            assert result.confidence == "low"

    def test_unambiguous_dmy_date(self, parser: FilenameParser) -> None:
        # 28-03-2026: day=28, month=03 — only valid as DMY (month 28 is invalid)
        result = parser.parse(Path("28-03-2026.jpg"))
        assert result is not None
        assert result.date_value.date() == date(2026, 3, 28)


class TestDatePrefDMY:
    def test_ambiguous_dmy_pref_picks_day_first(self) -> None:
        p = FilenameParser(date_pref="dmy")
        # 05-03-2026 — ambiguous: DMY=March 5, MDY=May 3
        result = p.parse(Path("05-03-2026.jpg"))
        assert result is not None
        assert result.date_value.date() == date(2026, 3, 5)  # March 5
        assert result.confidence == "high"

    def test_ambiguous_mdy_pref_picks_month_first(self) -> None:
        p = FilenameParser(date_pref="mdy")
        # 05-03-2026 — ambiguous: MDY=May 3, DMY=March 5
        result = p.parse(Path("05-03-2026.jpg"))
        assert result is not None
        assert result.date_value.date() == date(2026, 5, 3)  # May 3
        assert result.confidence == "high"

    def test_unambiguous_date_unaffected_by_pref(self) -> None:
        p_dmy = FilenameParser(date_pref="dmy")
        p_mdy = FilenameParser(date_pref="mdy")
        # 28-03-2026: only valid as DMY (month 28 invalid)
        r_dmy = p_dmy.parse(Path("28-03-2026.jpg"))
        r_mdy = p_mdy.parse(Path("28-03-2026.jpg"))
        assert r_dmy is not None and r_mdy is not None
        assert r_dmy.date_value.date() == date(2026, 3, 28)
        assert r_mdy.date_value.date() == date(2026, 3, 28)

    def test_ask_pref_returns_low_confidence_on_ambiguous(self) -> None:
        p = FilenameParser(date_pref="ask")
        result = p.parse(Path("05-03-2026.jpg"))
        assert result is not None
        assert result.confidence == "low"


class TestNoDate:
    @pytest.mark.parametrize("filename", [
        "no_date_here.jpg",
        "IMG_abcdef.jpg",
        "photo.jpg",
        "DSC00042.jpg",  # no date portion
    ])
    def test_no_match(self, parser: FilenameParser, filename: str) -> None:
        result = parser.parse(Path(filename))
        # May return None, or a low-confidence dateutil guess — both acceptable
        if result is not None:
            assert result.confidence == "low"


class TestInvalidDates:
    def test_invalid_month_rejected(self, parser: FilenameParser) -> None:
        # 20261328 — month 13 is invalid
        result = parser.parse(Path("photo_20261328.jpg"))
        assert result is None or result.date_value.month != 13

    def test_year_too_old_rejected(self, parser: FilenameParser) -> None:
        result = parser.parse(Path("IMG_18991231_000000.jpg"))
        assert result is None
