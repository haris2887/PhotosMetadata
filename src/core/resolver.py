from __future__ import annotations

import logging
from dataclasses import replace

from models.photo_file import DateSource, PhotoFile
from utils.date_utils import dates_within_hours

logger = logging.getLogger(__name__)

_CONFLICT_TOLERANCE_HOURS = 24


class DateResolver:
    def resolve(self, file: PhotoFile) -> PhotoFile:
        """
        Apply resolution rules and return a new PhotoFile with status and chosen_date set.
        This is a pure function — it never mutates the input.
        """
        # Rule 1: EXIF date already present
        if file.exif_date is not None:
            return replace(file, status="has_exif", chosen_date=file.exif_date)

        sources = file.alternate_sources

        # Rule 2: no sources at all
        if not sources:
            return replace(file, status="missing", chosen_date=None)

        # Rule 3: exactly one source
        if len(sources) == 1:
            return replace(file, status="resolved_single", chosen_date=sources[0].date_value)

        # Rule 4+: multiple sources — check if they agree
        if self._all_agree(sources):
            best = self._highest_confidence(sources)
            logger.debug("Sources agree for %s → %s", file.path.name, best.date_value)
            return replace(file, status="resolved_single", chosen_date=best.date_value)

        # Rule 5: sources disagree — user must pick
        logger.debug("Date conflict for %s: %s", file.path.name,
                     [(s.source_type, s.date_value) for s in sources])
        return replace(file, status="resolved_conflict", chosen_date=None)

    def _all_agree(self, sources: list[DateSource]) -> bool:
        """Return True if all sources are within the conflict tolerance of each other."""
        dates = [s.date_value for s in sources]
        return all(
            dates_within_hours(dates[0], d, hours=_CONFLICT_TOLERANCE_HOURS)
            for d in dates[1:]
        )

    def _highest_confidence(self, sources: list[DateSource]) -> DateSource:
        order = {"high": 0, "medium": 1, "low": 2}
        return min(sources, key=lambda s: order[s.confidence])
