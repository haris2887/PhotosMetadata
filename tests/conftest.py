from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Allow imports from src/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _exiftool_available() -> bool:
    try:
        result = subprocess.run(
            ["exiftool", "-ver"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "requires_exiftool: marks tests that need ExifTool installed"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if _exiftool_available():
        return
    skip = pytest.mark.skip(reason="ExifTool not found in PATH")
    for item in items:
        if item.get_closest_marker("requires_exiftool"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def jpeg_no_exif(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A minimal valid JPEG with no EXIF data, reused for the whole test session."""
    from PIL import Image

    path = tmp_path_factory.mktemp("fixtures") / "no_exif.jpg"
    img = Image.new("RGB", (8, 8), color=(100, 150, 200))
    img.save(path, format="JPEG")
    return path


@pytest.fixture()
def writable_jpeg(jpeg_no_exif: Path, tmp_path: Path) -> Path:
    """A per-test copy of jpeg_no_exif that tests can safely write to."""
    dest = tmp_path / "test_photo.jpg"
    shutil.copy(jpeg_no_exif, dest)
    return dest
