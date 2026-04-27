from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.exceptions import JsonParseError
from core.json_reader import GoogleJsonReader


@pytest.fixture
def reader() -> GoogleJsonReader:
    return GoogleJsonReader()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestFindJson:
    def test_finds_standard_sidecar(self, tmp_path: Path,
                                    reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042.jpg"
        photo.touch()
        sidecar = tmp_path / "IMG_0042.jpg.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_finds_stem_only_sidecar(self, tmp_path: Path,
                                     reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042.jpg"
        photo.touch()
        sidecar = tmp_path / "IMG_0042.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_prefers_full_name_over_stem(self, tmp_path: Path,
                                         reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042.jpg"
        photo.touch()
        full = tmp_path / "IMG_0042.jpg.json"
        stem = tmp_path / "IMG_0042.json"
        full.touch()
        stem.touch()
        assert reader.find_json(photo) == full

    def test_returns_none_when_missing(self, tmp_path: Path,
                                       reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042.jpg"
        photo.touch()
        assert reader.find_json(photo) is None

    def test_finds_duplicate_cleaned_name(self, tmp_path: Path,
                                          reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042(1).jpg"
        photo.touch()
        sidecar = tmp_path / "IMG_0042.jpg.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar


class TestReadDate:
    def test_reads_photo_taken_time(self, tmp_path: Path,
                                    reader: GoogleJsonReader) -> None:
        json_path = tmp_path / "photo.jpg.json"
        write_json(json_path, {
            "photoTakenTime": {"timestamp": "1711622400", "formatted": "..."},
        })
        result = reader.read_date(json_path)
        assert result is not None
        assert result.source_type == "google_json"
        assert result.confidence == "high"
        assert result.date_value.year == 2024

    def test_falls_back_to_creation_time(self, tmp_path: Path,
                                         reader: GoogleJsonReader) -> None:
        json_path = tmp_path / "photo.jpg.json"
        write_json(json_path, {
            "creationTime": {"timestamp": "1711622400"},
        })
        result = reader.read_date(json_path)
        assert result is not None
        assert result.confidence == "medium"

    def test_prefers_photo_taken_over_creation(self, tmp_path: Path,
                                               reader: GoogleJsonReader) -> None:
        json_path = tmp_path / "photo.jpg.json"
        write_json(json_path, {
            "photoTakenTime": {"timestamp": "1000000000"},
            "creationTime":   {"timestamp": "1711622400"},
        })
        result = reader.read_date(json_path)
        assert result is not None
        assert result.confidence == "high"
        assert result.raw_value == "1000000000"

    def test_returns_none_when_no_timestamps(self, tmp_path: Path,
                                             reader: GoogleJsonReader) -> None:
        json_path = tmp_path / "photo.jpg.json"
        write_json(json_path, {"title": "photo.jpg"})
        assert reader.read_date(json_path) is None

    def test_raises_on_malformed_json(self, tmp_path: Path,
                                      reader: GoogleJsonReader) -> None:
        json_path = tmp_path / "photo.jpg.json"
        json_path.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(JsonParseError):
            reader.read_date(json_path)
