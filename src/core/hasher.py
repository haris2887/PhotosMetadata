from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CHUNK = 65_536     # 64 KB — constant memory regardless of file size
HASH_ALGO = "md5"   # stored in cache rows so future algorithm changes are detectable


class FileHasher:
    """Stream-hash files using MD5 (stdlib only, no extra dependencies)."""

    def hash_file(self, path: Path) -> str:
        """
        Compute the MD5 hex digest of *path* by reading in 64 KB chunks.

        Raises OSError if the file cannot be opened or read.
        """
        h = hashlib.md5()
        with open(path, "rb") as fh:
            while chunk := fh.read(_CHUNK):
                h.update(chunk)
        return h.hexdigest()
