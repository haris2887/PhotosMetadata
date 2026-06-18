from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from core.hasher import HASH_ALGO

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".photosmetadata" / "backup_hashes.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS file_hashes (
    path      TEXT    PRIMARY KEY,
    hash      TEXT    NOT NULL,
    mtime     REAL    NOT NULL,
    size      INTEGER NOT NULL,
    algo      TEXT    NOT NULL,
    cached_at REAL    NOT NULL
);
"""


class HashCache:
    """
    SQLite-backed cache mapping (path, mtime, size) → md5 hex digest.

    A cache hit requires both mtime and size to match the stored values AND
    the stored algorithm to match the current HASH_ALGO.  If any differ the
    caller must rehash and call put() to update the row.

    Thread-safe: a threading.Lock serialises all writes; reads use a
    dedicated per-call connection to avoid blocking.
    """

    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(_CREATE_SQL)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, path: Path, mtime: float, size: int) -> str | None:
        """Return the cached hash if mtime, size, and algorithm all match."""
        row = self._conn.execute(
            "SELECT hash, mtime, size, algo FROM file_hashes WHERE path = ?",
            (str(path),),
        ).fetchone()
        if row is None:
            return None
        cached_hash, cached_mtime, cached_size, cached_algo = row
        if cached_algo == HASH_ALGO and cached_mtime == mtime and cached_size == size:
            return cached_hash
        return None

    def put(self, path: Path, mtime: float, size: int, hash_value: str) -> None:
        """Insert or replace a cache row (thread-safe)."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO file_hashes
                    (path, hash, mtime, size, algo, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(path), hash_value, mtime, size, HASH_ALGO, time.time()),
            )
            self._conn.commit()

    def clear_all(self) -> None:
        """Delete every cached row — triggered by the 'Force Re-Hash' button."""
        with self._lock:
            self._conn.execute("DELETE FROM file_hashes")
            self._conn.commit()
        logger.info("Hash cache cleared")

    def close(self) -> None:
        self._conn.close()
