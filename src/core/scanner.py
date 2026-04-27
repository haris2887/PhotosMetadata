from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    # Photos
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".raw", ".cr2", ".cr3",
    ".nef", ".arw", ".dng", ".orf", ".rw2",
    # Videos
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp",
})


class FileScanner:
    def scan(self, root: Path) -> list[Path]:
        """Recursively walk root and return all supported photo/video paths."""
        if not root.exists():
            logger.warning("Scan root does not exist: %s", root)
            return []
        if not root.is_dir():
            logger.warning("Scan root is not a directory: %s", root)
            return []

        found: list[Path] = []
        for path in root.rglob("*"):
            if path.is_file() and self.is_supported(path):
                found.append(path)
        logger.debug("Scanned %s: found %d supported files", root, len(found))
        return found

    def is_supported(self, path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS
