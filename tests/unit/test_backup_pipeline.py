from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.backup_pipeline import BackupPipeline
from core.hash_cache import HashCache
from core.hasher import FileHasher
from core.scanner import FileScanner
from models.backup_file import BackupFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline(tmp_path: Path) -> BackupPipeline:
    db = tmp_path / "cache.db"
    return BackupPipeline(
        scanner=FileScanner(),
        hasher=FileHasher(),
        cache=HashCache(db_path=db),
    )


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

class TestDetectDuplicates:
    def test_no_duplicates(self) -> None:
        files = [
            BackupFile(Path("a.jpg"), Path("/src"), Path("a.jpg"), 1, hash_value="aaa"),
            BackupFile(Path("b.jpg"), Path("/src"), Path("b.jpg"), 1, hash_value="bbb"),
        ]
        BackupPipeline._detect_duplicates(files)
        assert all(f.status == "pending" for f in files)

    def test_marks_second_occurrence_as_duplicate(self) -> None:
        canonical = BackupFile(Path("a.jpg"), Path("/src"), Path("a.jpg"), 1, hash_value="same")
        dup = BackupFile(Path("b.jpg"), Path("/src"), Path("b.jpg"), 1, hash_value="same")
        BackupPipeline._detect_duplicates([canonical, dup])
        assert canonical.status == "pending"
        assert dup.status == "duplicate"
        assert dup.duplicate_of == Path("a.jpg")

    def test_marks_third_occurrence_as_duplicate(self) -> None:
        files = [
            BackupFile(Path("a.jpg"), Path("/src"), Path("a.jpg"), 1, hash_value="x"),
            BackupFile(Path("b.jpg"), Path("/src"), Path("b.jpg"), 1, hash_value="x"),
            BackupFile(Path("c.jpg"), Path("/src"), Path("c.jpg"), 1, hash_value="x"),
        ]
        BackupPipeline._detect_duplicates(files)
        assert files[0].status == "pending"
        assert files[1].status == "duplicate"
        assert files[2].status == "duplicate"

    def test_files_without_hash_skipped(self) -> None:
        f = BackupFile(Path("a.jpg"), Path("/src"), Path("a.jpg"), 1, hash_value=None, status="error")
        BackupPipeline._detect_duplicates([f])
        assert f.status == "error"


# ---------------------------------------------------------------------------
# Full pipeline: compare unique vs backed_up
# ---------------------------------------------------------------------------

class TestPipelineCompare:
    def test_unique_file_not_in_dest(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _write(src / "photo.jpg", b"unique content")
        dest.mkdir()

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src], dest)

        assert len(result.files) == 1
        assert result.files[0].status == "unique"

    def test_file_already_in_dest(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        content = b"backed up content"
        _write(src / "photo.jpg", content)
        _write(dest / "photo.jpg", content)   # same bytes → same hash

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src], dest)

        assert result.files[0].status == "backed_up"

    def test_duplicate_source_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        content = b"same content"
        _write(src / "a.jpg", content)
        _write(src / "b.jpg", content)   # duplicate
        dest.mkdir()

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src], dest)

        statuses = {f.path.name: f.status for f in result.files}
        assert "unique" in statuses.values()
        assert "duplicate" in statuses.values()

    def test_multiple_sources(self, tmp_path: Path) -> None:
        src1 = tmp_path / "src1"
        src2 = tmp_path / "src2"
        dest = tmp_path / "dest"
        _write(src1 / "img1.jpg", b"content one")
        _write(src2 / "img2.jpg", b"content two")
        dest.mkdir()

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src1, src2], dest)

        assert result.total == 2
        assert all(f.status == "unique" for f in result.files)


# ---------------------------------------------------------------------------
# copy_unique: path construction and shutil.copy2 usage
# ---------------------------------------------------------------------------

class TestCopyUnique:
    def test_copies_file_preserving_structure(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _write(src / "2020" / "vacation" / "img.jpg", b"photo content")
        dest.mkdir()

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src], dest)

        assert result.unique, "expected one unique file"
        pipeline.copy_unique(result)

        expected = dest / "2020" / "vacation" / "img.jpg"
        assert expected.exists()
        assert expected.read_bytes() == b"photo content"

    def test_copy_subset(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _write(src / "a.jpg", b"aaa")
        _write(src / "b.jpg", b"bbb")
        dest.mkdir()

        pipeline = _make_pipeline(tmp_path)
        result = pipeline.run([src], dest)

        # Copy only one of the two unique files
        target = [f for f in result.unique if f.path.name == "a.jpg"]
        pipeline.copy_unique(result, files=target)

        assert (dest / "a.jpg").exists()
        assert not (dest / "b.jpg").exists()
