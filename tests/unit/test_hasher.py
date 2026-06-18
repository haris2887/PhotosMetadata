from __future__ import annotations

import hashlib

import pytest

from core.hasher import FileHasher, HASH_ALGO


@pytest.fixture()
def hasher() -> FileHasher:
    return FileHasher()


class TestFileHasher:
    def test_hash_known_content(self, hasher: FileHasher, tmp_path) -> None:
        f = tmp_path / "file.bin"
        f.write_bytes(b"hello world")
        expected = hashlib.md5(b"hello world").hexdigest()
        assert hasher.hash_file(f) == expected

    def test_hash_empty_file(self, hasher: FileHasher, tmp_path) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        expected = hashlib.md5(b"").hexdigest()
        assert hasher.hash_file(f) == expected

    def test_hash_large_content_streamed(self, hasher: FileHasher, tmp_path) -> None:
        data = b"A" * (200 * 1024)   # 200 KB — forces multiple 64 KB chunks
        f = tmp_path / "big.bin"
        f.write_bytes(data)
        expected = hashlib.md5(data).hexdigest()
        assert hasher.hash_file(f) == expected

    def test_different_content_different_hash(self, hasher: FileHasher, tmp_path) -> None:
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"alpha")
        f2.write_bytes(b"beta")
        assert hasher.hash_file(f1) != hasher.hash_file(f2)

    def test_same_content_same_hash(self, hasher: FileHasher, tmp_path) -> None:
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"same content")
        f2.write_bytes(b"same content")
        assert hasher.hash_file(f1) == hasher.hash_file(f2)

    def test_raises_on_missing_file(self, hasher: FileHasher, tmp_path) -> None:
        with pytest.raises(OSError):
            hasher.hash_file(tmp_path / "nonexistent.bin")

    def test_hash_algo_constant(self) -> None:
        assert HASH_ALGO == "md5"
