from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from core.exceptions import JsonParseError
from models.photo_file import DateSource

logger = logging.getLogger(__name__)

_DUPLICATE_SUFFIX = re.compile(r'\(\d+\)$')


class GoogleJsonReader:
    def find_json(self, photo_path: Path) -> Path | None:
        """
        Locate the Google Photos Takeout JSON sidecar for a photo file.
        Tries naming conventions in priority order.
        """
        name = photo_path.name    # "IMG_0042.jpg"
        stem = photo_path.stem    # "IMG_0042"
        parent = photo_path.parent

        candidates: list[Path] = [
            parent / f"{name}.json",   # IMG_0042.jpg.json  (most common)
            parent / f"{stem}.json",   # IMG_0042.json
        ]

        # Google appends (N) to the stem of duplicate filenames (e.g. IMG_0042(1).jpg)
        clean_stem = _DUPLICATE_SUFFIX.sub("", stem)
        if clean_stem != stem:
            clean_name = clean_stem + photo_path.suffix   # IMG_0042.jpg
            candidates += [
                parent / f"{clean_name}.json",            # IMG_0042.jpg.json
                parent / f"{clean_stem}.json",            # IMG_0042.json
            ]

        for candidate in candidates:
            if candidate.exists():
                logger.debug("Found JSON sidecar: %s", candidate)
                return candidate

        return None

    def read_date(self, json_path: Path) -> DateSource | None:
        """
        Parse a Google Takeout JSON file and return the best DateSource.
        Prefers photoTakenTime (confidence=high) over creationTime (confidence=medium).
        """
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise JsonParseError(f"Cannot read {json_path}: {exc}") from exc

        for key, confidence in [("photoTakenTime", "high"), ("creationTime", "medium")]:
            entry = data.get(key)
            if not entry:
                continue
            ts_str = entry.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = int(ts_str)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
                logger.debug("JSON date (%s): %s → %s", key, json_path.name, dt)
                return DateSource("google_json", dt, confidence, ts_str)  # type: ignore[arg-type]
            except (ValueError, OSError):
                continue

        logger.debug("No usable date found in JSON: %s", json_path)
        return None
