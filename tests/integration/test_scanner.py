from __future__ import annotations

from pathlib import Path

import pytest

from core.scanner import FileScanner, SUPPORTED_EXTENSIONS


@pytest.fixture
def scanner() -> FileScanner:
    return FileScanner()


class TestFileScanner:
    def test_finds_jpg(self, tmp_path: Path, scanner: FileScanner) -> None:
        (tmp_path / "photo.jpg").touch()
        results = scanner.scan(tmp_path)
        assert any(p.name == "photo.jpg" for p in results)

    def test_case_insensitive_extension(self, tmp_path: Path,
                                        scanner: FileScanner) -> None:
        (tmp_path / "photo.JPG").touch()
        (tmp_path / "video.MP4").touch()
        results = scanner.scan(tmp_path)
        assert len(results) == 2

    def test_ignores_unsupported_extensions(self, tmp_path: Path,
                                            scanner: FileScanner) -> None:
        (tmp_path / "document.pdf").touch()
        (tmp_path / "data.json").touch()
        (tmp_path / "photo.jpg").touch()
        results = scanner.scan(tmp_path)
        assert len(results) == 1
        assert results[0].name == "photo.jpg"

    def test_recursive_scan(self, tmp_path: Path, scanner: FileScanner) -> None:
        sub = tmp_path / "2024" / "vacation"
        sub.mkdir(parents=True)
        (sub / "IMG_001.jpg").touch()
        (tmp_path / "cover.png").touch()
        results = scanner.scan(tmp_path)
        assert len(results) == 2

    def test_empty_directory(self, tmp_path: Path, scanner: FileScanner) -> None:
        assert scanner.scan(tmp_path) == []

    def test_nonexistent_directory(self, scanner: FileScanner) -> None:
        assert scanner.scan(Path("/nonexistent/path/xyz")) == []

    def test_all_supported_extensions_recognised(self, scanner: FileScanner) -> None:
        for ext in SUPPORTED_EXTENSIONS:
            assert scanner.is_supported(Path(f"file{ext}"))
            assert scanner.is_supported(Path(f"file{ext.upper()}"))
