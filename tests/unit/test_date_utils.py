from datetime import datetime

import pytest

from utils.date_utils import (
    dates_within_hours,
    datetime_to_exif_str,
    exif_str_to_datetime,
    normalize_to_date_only,
)


class TestDatetimeToExifStr:
    def test_standard(self) -> None:
        dt = datetime(2026, 3, 28, 14, 30, 0)
        assert datetime_to_exif_str(dt) == "2026:03:28 14:30:00"

    def test_midnight(self) -> None:
        dt = datetime(2024, 1, 1, 0, 0, 0)
        assert datetime_to_exif_str(dt) == "2024:01:01 00:00:00"

    def test_roundtrip(self) -> None:
        dt = datetime(2023, 11, 5, 9, 7, 3)
        assert exif_str_to_datetime(datetime_to_exif_str(dt)) == dt


class TestExifStrToDatetime:
    def test_valid(self) -> None:
        result = exif_str_to_datetime("2026:03:28 14:30:00")
        assert result == datetime(2026, 3, 28, 14, 30, 0)

    def test_empty_string(self) -> None:
        assert exif_str_to_datetime("") is None

    def test_zero_date(self) -> None:
        assert exif_str_to_datetime("0000:00:00 00:00:00") is None

    def test_whitespace_stripped(self) -> None:
        result = exif_str_to_datetime("  2026:03:28 14:30:00  ")
        assert result == datetime(2026, 3, 28, 14, 30, 0)

    def test_invalid_format(self) -> None:
        assert exif_str_to_datetime("not-a-date") is None

    def test_date_only_fallback(self) -> None:
        result = exif_str_to_datetime("2026:03:28")
        assert result == datetime(2026, 3, 28, 0, 0, 0)


class TestNormalizeToDateOnly:
    def test_strips_time(self) -> None:
        dt = datetime(2026, 3, 28, 14, 30, 59)
        result = normalize_to_date_only(dt)
        assert result == datetime(2026, 3, 28, 0, 0, 0)

    def test_already_midnight(self) -> None:
        dt = datetime(2026, 3, 28, 0, 0, 0)
        assert normalize_to_date_only(dt) == dt


class TestDatesWithinHours:
    def test_same_datetime(self) -> None:
        dt = datetime(2026, 3, 28, 12, 0, 0)
        assert dates_within_hours(dt, dt) is True

    def test_within_24h(self) -> None:
        a = datetime(2026, 3, 28, 0, 0, 0)
        b = datetime(2026, 3, 28, 23, 59, 59)
        assert dates_within_hours(a, b, hours=24) is True

    def test_exactly_24h_is_not_within(self) -> None:
        a = datetime(2026, 3, 28, 0, 0, 0)
        b = datetime(2026, 3, 29, 0, 0, 0)
        assert dates_within_hours(a, b, hours=24) is False

    def test_far_apart(self) -> None:
        a = datetime(2026, 1, 1)
        b = datetime(2026, 6, 1)
        assert dates_within_hours(a, b) is False

    def test_custom_tolerance(self) -> None:
        a = datetime(2026, 3, 28, 0, 0, 0)
        b = datetime(2026, 3, 28, 1, 0, 0)
        assert dates_within_hours(a, b, hours=2) is True
        assert dates_within_hours(a, b, hours=1) is False
