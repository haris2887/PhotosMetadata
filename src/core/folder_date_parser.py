from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from models.photo_file import DateSource

logger = logging.getLogger(__name__)

_MIN_YEAR = 1900


def _max_year() -> int:
    return datetime.now().year + 1


def _valid_date(year: int, month: int, day: int) -> datetime | None:
    try:
        if not (_MIN_YEAR <= year <= _max_year()):
            return None
        return datetime(year, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_MONTH_MAP: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_NAMES_PATTERN = (
    r"january|february|march|april|may|june|july|august|september|"
    r"october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec"
)

# 4-digit year in range 1900-2099
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# Month name as an isolated word/token
_MONTH_NAME_RE = re.compile(rf"\b({_MONTH_NAMES_PATTERN})\b", re.IGNORECASE)

# "September-24" / "September 24" / "September_24"
_MONTH_NAME_DAY_RE = re.compile(
    rf"\b({_MONTH_NAMES_PATTERN})[_\- ]?(\d{{1,2}})\b", re.IGNORECASE
)

# Numeric "09-24" / "9/24" / "09_24"
_MONTH_DAY_NUM_RE = re.compile(r"\b(0?[1-9]|1[0-2])[_\-/](0?[1-9]|[12]\d|3[01])\b")

# Full date in one part: YYYY-MM-DD / YYYY/MM/DD
_FULL_DATE_SEP_RE = re.compile(r"\b(\d{4})[_\-/](\d{1,2})[_\-/](\d{1,2})\b")

# Compact: YYYYMMDD
_FULL_DATE_COMPACT_RE = re.compile(
    r"\b((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b"
)

# Numeric month-only as the entire string (no stray digits that could be a day)
_MONTH_ONLY_NUM_RE = re.compile(r"^\s*(0?[1-9]|1[0-2])\s*$")

# Drive letters and UNC components to skip
_SKIP_RE = re.compile(r"^([A-Za-z]:|\\\\|/)$")


def _extract_year(s: str) -> int | None:
    m = _YEAR_RE.search(s)
    if m:
        y = int(m.group(1))
        if _MIN_YEAR <= y <= _max_year():
            return y
    return None


def _extract_month(s: str) -> int | None:
    """Return a month number from a string that contains a month name or bare month number."""
    m = _MONTH_NAME_RE.search(s)
    if m:
        return _MONTH_MAP[m.group(1).lower()]
    m = _MONTH_ONLY_NUM_RE.match(s)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class FolderDateParser:
    """
    Extracts a date from the directory path of a photo file.

    Search strategy (most to least specific):

    Pass 1 — full date (Y+M+D) from a single directory component
      Handles: "2020-09-24", "20200924"

    Pass 2 — full date assembled from two adjacent components
      Handles: "2020" + "September-24", "2020" + "09-24"

    Pass 3 — full date assembled from three adjacent components
      Handles: "2020" + "September" + "24", "2020" + "09" + "24"

    Pass 4 — year + month (no day), single or two components
      Handles: "Photos from September 2020", "2020" + "September"

    Pass 5 — year only from any component
      Handles: "Photos from 2020", "2023"

    Returns DateSource with:
      confidence="medium"  for year+month+day   (participates in resolver)
      confidence="low"     for year+month only   (shown in table; not used by resolver)
      confidence="low"     for year only         (shown in table; not used by resolver)
    """

    def parse(self, path: Path) -> DateSource | None:
        parts = [
            p for p in path.parent.parts
            if p and not _SKIP_RE.match(p)
        ]
        if not parts:
            return None

        # Pass 1 — full date from single component (innermost first)
        for part in reversed(parts):
            result = self._single_full(part)
            if result:
                return result

        # Pass 2 — full date from two adjacent components
        for i in range(len(parts) - 1, 0, -1):
            result = self._pair_full(parts[i - 1], parts[i])
            if result:
                return result

        # Pass 3 — full date from three adjacent components
        for i in range(len(parts) - 1, 1, -1):
            result = self._triple_full(parts[i - 2], parts[i - 1], parts[i])
            if result:
                return result

        # Pass 4 — year+month (partial) from single or two components
        for part in reversed(parts):
            result = self._single_ym(part)
            if result:
                return result
        for i in range(len(parts) - 1, 0, -1):
            result = self._pair_ym(parts[i - 1], parts[i])
            if result:
                return result

        # Pass 5 — year only (innermost first)
        for part in reversed(parts):
            y = _extract_year(part)
            if y is not None:
                return DateSource("folder_path", datetime(y, 1, 1), "low", part)

        return None

    # ------------------------------------------------------------------
    # Pass 1 helpers
    # ------------------------------------------------------------------

    def _single_full(self, part: str) -> DateSource | None:
        m = _FULL_DATE_SEP_RE.search(part)
        if m:
            dt = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if dt:
                return DateSource("folder_path", dt, "medium", part)

        m = _FULL_DATE_COMPACT_RE.search(part)
        if m:
            dt = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if dt:
                return DateSource("folder_path", dt, "medium", part)

        return None

    # ------------------------------------------------------------------
    # Pass 2 helpers
    # ------------------------------------------------------------------

    def _pair_full(self, a: str, b: str) -> DateSource | None:
        """Assemble a full date from two adjacent directory names."""
        raw = f"{a}/{b}"

        # Determine which part holds the year
        year_a = _extract_year(a)
        year_b = _extract_year(b)

        for year, other in [(year_a, b), (year_b, a)]:
            if year is None:
                continue

            # MonthName-Day in *other*
            md = _MONTH_NAME_DAY_RE.search(other)
            if md:
                month = _MONTH_MAP[md.group(1).lower()]
                day = int(md.group(2))
                dt = _valid_date(year, month, day)
                if dt:
                    return DateSource("folder_path", dt, "medium", raw)

            # Numeric MM-DD in *other*
            md_num = _MONTH_DAY_NUM_RE.search(other)
            if md_num:
                month = int(md_num.group(1))
                day = int(md_num.group(2))
                dt = _valid_date(year, month, day)
                if dt:
                    return DateSource("folder_path", dt, "medium", raw)

        return None

    # ------------------------------------------------------------------
    # Pass 3 helper
    # ------------------------------------------------------------------

    def _triple_full(self, a: str, b: str, c: str) -> DateSource | None:
        """Assemble a full date from three adjacent directory names."""
        raw = f"{a}/{b}/{c}"

        # Find year among the three
        year: int | None = None
        remaining: list[str] = []
        for part in [a, b, c]:
            y = _extract_year(part)
            if y is not None and year is None:
                year = y
            else:
                remaining.append(part)

        if year is None or len(remaining) < 2:
            return None

        # Try: month from remaining[0], day from remaining[1]
        for month_part, day_part in [(remaining[0], remaining[1]),
                                     (remaining[1], remaining[0])]:
            month = _extract_month(month_part)
            if month is None:
                continue
            day_m = re.search(r"\b(\d{1,2})\b", day_part)
            if day_m:
                day = int(day_m.group(1))
                dt = _valid_date(year, month, day)
                if dt:
                    return DateSource("folder_path", dt, "medium", raw)

        return None

    # ------------------------------------------------------------------
    # Pass 4 helpers — year+month only (low confidence)
    # ------------------------------------------------------------------

    def _single_ym(self, part: str) -> DateSource | None:
        """Year + month name in a single directory component."""
        year = _extract_year(part)
        if year is None:
            return None
        month = _extract_month(part)
        if month is not None:
            return DateSource(
                "folder_path", datetime(year, month, 1), "low", part
            )
        return None

    def _pair_ym(self, a: str, b: str) -> DateSource | None:
        """Year in one part, month in the other (no day)."""
        raw = f"{a}/{b}"
        for year_part, month_part in [(a, b), (b, a)]:
            year = _extract_year(year_part)
            if year is None:
                continue
            # Only use other part for month if it doesn't also have a year
            # (avoids matching two-year pairs like "2019/2020")
            if _extract_year(month_part) is not None:
                continue
            month = _extract_month(month_part)
            if month is not None:
                return DateSource(
                    "folder_path", datetime(year, month, 1), "low", raw
                )
        return None
