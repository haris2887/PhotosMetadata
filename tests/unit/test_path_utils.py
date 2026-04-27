from pathlib import Path

from utils.path_utils import get_relative_display_path, safe_stem


class TestGetRelativeDisplayPath:
    def test_relative(self) -> None:
        root = Path("/photos")
        path = Path("/photos/2024/IMG_001.jpg")
        assert get_relative_display_path(path, root) == "2024/IMG_001.jpg"

    def test_same_dir(self) -> None:
        root = Path("/photos")
        path = Path("/photos/IMG_001.jpg")
        assert get_relative_display_path(path, root) == "IMG_001.jpg"

    def test_unrelated_path_returns_full(self) -> None:
        root = Path("/photos")
        path = Path("/other/IMG_001.jpg")
        assert get_relative_display_path(path, root) == "/other/IMG_001.jpg"


class TestSafeStem:
    def test_single_extension(self) -> None:
        assert safe_stem(Path("IMG_001.jpg")) == "IMG_001"

    def test_double_extension(self) -> None:
        assert safe_stem(Path("photo.jpg.json")) == "photo"

    def test_no_extension(self) -> None:
        assert safe_stem(Path("noext")) == "noext"

    def test_triple_extension(self) -> None:
        assert safe_stem(Path("file.tar.gz.bak")) == "file"
