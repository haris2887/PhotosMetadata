from __future__ import annotations

from pathlib import Path

import pytest

from core.hash_cache import HashCache


@pytest.fixture()
def cache(tmp_path) -> HashCache:
    db = tmp_path / "test_hashes.db"
    c = HashCache(db_path=db)
    yield c
    c.close()


class TestHashCache:
    def test_miss_on_empty_cache(self, cache: HashCache, tmp_path) -> None:
        p = tmp_path / "img.jpg"
        assert cache.get(p, mtime=1000.0, size=512) is None

    def test_put_then_get_hit(self, cache: HashCache, tmp_path) -> None:
        p = tmp_path / "img.jpg"
        cache.put(p, mtime=1000.0, size=512, hash_value="abc123")
        assert cache.get(p, mtime=1000.0, size=512) == "abc123"

    def test_miss_when_mtime_changed(self, cache: HashCache, tmp_path) -> None:
        p = tmp_path / "img.jpg"
        cache.put(p, mtime=1000.0, size=512, hash_value="abc123")
        assert cache.get(p, mtime=9999.0, size=512) is None

    def test_miss_when_size_changed(self, cache: HashCache, tmp_path) -> None:
        p = tmp_path / "img.jpg"
        cache.put(p, mtime=1000.0, size=512, hash_value="abc123")
        assert cache.get(p, mtime=1000.0, size=999) is None

    def test_put_replaces_stale_row(self, cache: HashCache, tmp_path) -> None:
        p = tmp_path / "img.jpg"
        cache.put(p, mtime=1000.0, size=512, hash_value="old_hash")
        cache.put(p, mtime=2000.0, size=512, hash_value="new_hash")
        assert cache.get(p, mtime=2000.0, size=512) == "new_hash"
        assert cache.get(p, mtime=1000.0, size=512) is None

    def test_multiple_files_independent(self, cache: HashCache, tmp_path) -> None:
        p1 = tmp_path / "a.jpg"
        p2 = tmp_path / "b.jpg"
        cache.put(p1, mtime=1.0, size=10, hash_value="hash_a")
        cache.put(p2, mtime=2.0, size=20, hash_value="hash_b")
        assert cache.get(p1, mtime=1.0, size=10) == "hash_a"
        assert cache.get(p2, mtime=2.0, size=20) == "hash_b"

    def test_clear_all_removes_all_rows(self, cache: HashCache, tmp_path) -> None:
        p1 = tmp_path / "a.jpg"
        p2 = tmp_path / "b.jpg"
        cache.put(p1, mtime=1.0, size=10, hash_value="hash_a")
        cache.put(p2, mtime=2.0, size=20, hash_value="hash_b")
        cache.clear_all()
        assert cache.get(p1, mtime=1.0, size=10) is None
        assert cache.get(p2, mtime=2.0, size=20) is None

    def test_db_file_created(self, tmp_path) -> None:
        db = tmp_path / "subdir" / "hashes.db"
        c = HashCache(db_path=db)
        c.close()
        assert db.exists()
