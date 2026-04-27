from __future__ import annotations

from datetime import datetime


EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"


def datetime_to_exif_str(dt: datetime) -> str:
    """Format a datetime to ExifTool's expected string: '2026:03:28 14:30:00'."""
    return dt.strftime(EXIF_DATE_FORMAT)


def exif_str_to_datetime(s: str) -> datetime | None:
    """Parse ExifTool's date string format. Returns None on any parse failure."""
    s = s.strip()
    if not s or s.startswith("0000"):
        return None
    try:
        return datetime.strptime(s, EXIF_DATE_FORMAT)
    except ValueError:
        # Some tools write partial dates — try date-only fallback
        try:
            return datetime.strptime(s[:10], "%Y:%m:%d")
        except ValueError:
            return None


def normalize_to_date_only(dt: datetime) -> datetime:
    """Return a datetime with the time component zeroed out."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def dates_within_hours(a: datetime, b: datetime, hours: int = 24) -> bool:
    """Return True if two datetimes differ by less than `hours`."""
    return abs((a - b).total_seconds()) < hours * 3600
