from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from models.photo_file import DateSource

logger = logging.getLogger(__name__)

# Year sanity bounds
_MIN_YEAR = 1900
_MAX_YEAR_OFFSET = 1  # allow up to 1 year in the future


def _max_year() -> int:
    return datetime.now().year + _MAX_YEAR_OFFSET


def _valid_date(year: int, month: int, day: int) -> datetime | None:
    """Return a datetime if the values form a valid date, else None."""
    try:
        if not (_MIN_YEAR <= year <= _max_year()):
            return None
        return datetime(year, month, day)
    except ValueError:
        return None


# ── Layer 1: named camera-prefix patterns (confidence=high) ──────────────────
_CAMERA_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Android / Samsung: IMG_20260328_142201, VID_20260328, MVIMG_20260328
    (re.compile(r'(?:IMG|VID|MVIMG|PANO)[_-](\d{4})(\d{2})(\d{2})'), "camera_prefix"),
    # Samsung screenshots: Screenshot_20260328-142201, Screenshot_2026-03-28
    (re.compile(r'Screenshot[_-](\d{4})[_-]?(\d{2})[_-]?(\d{2})'), "screenshot"),
    # WhatsApp: WA0001-20260328
    (re.compile(r'WA\d+[_-](\d{4})(\d{2})(\d{2})'), "whatsapp"),
    # DSC / Canon: DSC_20260328
    (re.compile(r'DSC[_-](\d{4})(\d{2})(\d{2})'), "dsc"),
]

# ── Layer 2: bare ISO-8601 anywhere in filename (confidence=high) ─────────────
_ISO_SEP = re.compile(r'(?<!\d)(\d{4})[_\-](\d{2})[_\-](\d{2})(?!\d)')
# Compact ISO only when 8 contiguous digits stand alone (not inside a longer run)
_ISO_COMPACT = re.compile(r'(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)')

# ── Layer 3: ambiguous DMY or MDY (confidence=low) ────────────────────────────
_AMBIGUOUS = re.compile(r'(?<!\d)(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})(?!\d)')


class FilenameParser:
    def parse(self, path: Path) -> DateSource | None:
        """
        Return the best DateSource from the filename, or None if no date found.
        When the date is ambiguous (DMY vs MDY and both valid), returns the first
        valid interpretation with confidence='low' so the resolver can flag a conflict.
        """
        stem = path.stem

        # Layer 1 — camera prefix (highest confidence)
        for pattern, label in _CAMERA_PATTERNS:
            m = pattern.search(stem)
            if m:
                dt = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if dt:
                    logger.debug("Filename date (%s): %s → %s", label, stem, dt)
                    return DateSource("filename", dt, "high", stem)

        # Layer 2 — separated ISO-8601 (YYYY-MM-DD)
        m = _ISO_SEP.search(stem)
        if m:
            dt = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if dt:
                logger.debug("Filename date (iso_sep): %s → %s", stem, dt)
                return DateSource("filename", dt, "high", stem)

        # Layer 2 — compact ISO-8601 (YYYYMMDD) only when clearly isolated
        m = _ISO_COMPACT.search(stem)
        if m:
            dt = _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if dt:
                logger.debug("Filename date (iso_compact): %s → %s", stem, dt)
                return DateSource("filename", dt, "high", stem)

        # Layer 3 — ambiguous DD/MM/YYYY or MM/DD/YYYY
        m = _AMBIGUOUS.search(stem)
        if m:
            a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dt = _valid_date(year, b, a) or _valid_date(year, a, b)
            if dt:
                logger.debug("Filename date (ambiguous): %s → %s (low confidence)", stem, dt)
                return DateSource("filename", dt, "low", stem)

        # Layer 4 — dateutil fuzzy fallback
        return self._dateutil_fallback(stem)

    def _dateutil_fallback(self, stem: str) -> DateSource | None:
        try:
            from dateutil.parser import ParserError, parse as dateutil_parse

            dt = dateutil_parse(stem, fuzzy=True)
            if _MIN_YEAR <= dt.year <= _max_year():
                logger.debug("Filename date (dateutil): %s → %s", stem, dt)
                return DateSource("filename", dt.replace(hour=0, minute=0, second=0),
                                  "low", stem)
        except Exception:
            pass
        return None
