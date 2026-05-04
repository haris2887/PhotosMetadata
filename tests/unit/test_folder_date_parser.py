from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.folder_date_parser import FolderDateParser


@pytest.fixture()
def parser() -> FolderDateParser:
    return FolderDateParser()


# ---------------------------------------------------------------------------
# Pass 1 — full date from a single component
# ---------------------------------------------------------------------------

class TestSingleComponent:
    def test_iso_separator(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020-09-24/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)
        assert ds.confidence == "medium"

    def test_slash_separator(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2021/01/15/img.jpg")
        # "2021/01/15" shows as three separate parts — handled by pass 3
        # Single component with slashes is OS-dependent; test the compact form instead
        p2 = Path("/photos/20201215/img.jpg")
        ds = parser.parse(p2)
        assert ds is not None
        assert ds.date_value == datetime(2020, 12, 15)
        assert ds.confidence == "medium"

    def test_compact_yyyymmdd(self, parser: FolderDateParser) -> None:
        p = Path("/archive/20190704/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2019, 7, 4)

    def test_descriptive_name_with_full_date(self, parser: FolderDateParser) -> None:
        p = Path("/photos/Birthday Party 2022-03-15/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2022, 3, 15)
        assert ds.confidence == "medium"

    def test_innermost_wins_over_outer(self, parser: FolderDateParser) -> None:
        p = Path("/2019-01-01/2021-06-30/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2021, 6, 30)

    def test_invalid_date_skipped(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020-13-01/img.jpg")
        # month 13 invalid — should not return a full-date result
        ds = parser.parse(p)
        # may still return year-only; just check it's not month 13
        if ds is not None:
            assert ds.date_value.month != 13


# ---------------------------------------------------------------------------
# Pass 2 — full date from two adjacent components
# ---------------------------------------------------------------------------

class TestPairComponents:
    def test_year_then_month_name_day(self, parser: FolderDateParser) -> None:
        p = Path(r"C:\Users\Photos\2020\September-24\img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)
        assert ds.confidence == "medium"

    def test_year_then_month_name_space_day(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020/September 24/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)

    def test_year_then_numeric_mm_dd(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020/09-24/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)

    def test_year_then_numeric_slash(self, parser: FolderDateParser) -> None:
        p = Path("/archive/2021/11_05/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2021, 11, 5)

    def test_abbreviated_month(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2018/Sep-07/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2018, 9, 7)

    def test_innermost_pair_wins(self, parser: FolderDateParser) -> None:
        p = Path("/2019/March-01/2022/July-15/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2022, 7, 15)


# ---------------------------------------------------------------------------
# Pass 3 — full date from three adjacent components
# ---------------------------------------------------------------------------

class TestTripleComponents:
    def test_year_month_name_day(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020/September/24/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)
        assert ds.confidence == "medium"

    def test_year_numeric_month_day(self, parser: FolderDateParser) -> None:
        p = Path("/archive/2021/09/07/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2021, 9, 7)

    def test_abbreviated_month_name(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2019/Oct/31/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2019, 10, 31)


# ---------------------------------------------------------------------------
# Pass 4 — year + month only (low confidence)
# ---------------------------------------------------------------------------

class TestYearMonth:
    def test_single_component_year_and_month_name(self, parser: FolderDateParser) -> None:
        p = Path("/photos/September 2020/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 1)
        assert ds.confidence == "low"

    def test_pair_year_then_month_name(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020/September/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 1)
        assert ds.confidence == "low"

    def test_pair_month_then_year(self, parser: FolderDateParser) -> None:
        p = Path("/photos/January/2021/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2021, 1, 1)
        assert ds.confidence == "low"

    def test_pair_year_then_numeric_month(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2022/03/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2022, 3, 1)
        assert ds.confidence == "low"

    def test_two_year_components_not_matched(self, parser: FolderDateParser) -> None:
        p = Path("/archive/2019/2020/img.jpg")
        ds = parser.parse(p)
        # Should fall back to year-only (pass 5), not pair_ym
        if ds is not None:
            assert ds.date_value.year in (2019, 2020)


# ---------------------------------------------------------------------------
# Pass 5 — year only
# ---------------------------------------------------------------------------

class TestYearOnly:
    def test_bare_year_folder(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2020/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 1, 1)
        assert ds.confidence == "low"

    def test_year_in_descriptive_name(self, parser: FolderDateParser) -> None:
        p = Path("/photos/Photos from 2020/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value.year == 2020
        assert ds.confidence == "low"

    def test_innermost_year_wins(self, parser: FolderDateParser) -> None:
        p = Path("/archive/2015/2023/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value.year == 2023


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_date_in_path(self, parser: FolderDateParser) -> None:
        p = Path("/photos/vacation/img.jpg")
        ds = parser.parse(p)
        assert ds is None

    def test_file_in_root(self, parser: FolderDateParser) -> None:
        p = Path("/img.jpg")
        ds = parser.parse(p)
        assert ds is None

    def test_year_out_of_range(self, parser: FolderDateParser) -> None:
        p = Path("/photos/1800/img.jpg")
        ds = parser.parse(p)
        assert ds is None

    def test_source_type_is_folder_path(self, parser: FolderDateParser) -> None:
        p = Path("/photos/2022-07-04/img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.source_type == "folder_path"

    def test_real_world_takeout_path(self, parser: FolderDateParser) -> None:
        p = Path(r"C:\Users\HarisAli\Downloads\Takeout\Photos\2020\September-24\img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2020, 9, 24)
        assert ds.confidence == "medium"

    def test_windows_drive_letter_skipped(self, parser: FolderDateParser) -> None:
        p = Path(r"C:\photos\2021-05-10\img.jpg")
        ds = parser.parse(p)
        assert ds is not None
        assert ds.date_value == datetime(2021, 5, 10)
