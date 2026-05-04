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

    def test_finds_supplemental_metadata_sidecar(self, tmp_path: Path,
                                                  reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG-20180713-WA0001.jpg"
        photo.touch()
        sidecar = tmp_path / "IMG-20180713-WA0001.jpg.supplemental-metadata.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_finds_stem_supplemental_metadata_sidecar(self, tmp_path: Path,
                                                       reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG-20180713-WA0001.jpg"
        photo.touch()
        sidecar = tmp_path / "IMG-20180713-WA0001.supplemental-metadata.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_prefers_classic_json_over_supplemental(self, tmp_path: Path,
                                                     reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042.jpg"
        photo.touch()
        classic = tmp_path / "IMG_0042.jpg.json"
        supplemental = tmp_path / "IMG_0042.jpg.supplemental-metadata.json"
        classic.touch()
        supplemental.touch()
        assert reader.find_json(photo) == classic

    def test_finds_supplemental_for_duplicate_filename(self, tmp_path: Path,
                                                        reader: GoogleJsonReader) -> None:
        photo = tmp_path / "IMG_0042(1).jpg"
        photo.touch()
        sidecar = tmp_path / "IMG_0042.jpg.supplemental-metadata.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_finds_json_via_alternate_extension(self, tmp_path: Path,
                                                reader: GoogleJsonReader) -> None:
        # File was originally photo.png (wrong ext); renamed to photo.jpg by magic-byte
        # fixer. JSON is still named photo.png.json.
        photo = tmp_path / "photo.jpg"
        photo.touch()
        sidecar = tmp_path / "photo.png.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_finds_json_via_alternate_extension_supplemental(self, tmp_path: Path,
                                                              reader: GoogleJsonReader) -> None:
        photo = tmp_path / "photo.jpg"
        photo.touch()
        sidecar = tmp_path / "photo.png.supplemental-metadata.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_prefers_matching_extension_over_alternate(self, tmp_path: Path,
                                                        reader: GoogleJsonReader) -> None:
        # Both photo.jpg.json and photo.png.json exist — prefer the one whose
        # extension matches the current file.
        photo = tmp_path / "photo.jpg"
        photo.touch()
        correct = tmp_path / "photo.jpg.json"
        alternate = tmp_path / "photo.png.json"
        correct.touch()
        alternate.touch()
        assert reader.find_json(photo) == correct

    def test_finds_json_in_original_dir_when_moved_to_unwritable(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        # Simulate: scan root is tmp_path; file was at subdir/photo.jpg with JSON;
        # file was moved to _unwritable/subdir/photo.jpg but JSON was left behind.
        scan_root = tmp_path
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        unwritable_subdir = tmp_path / "_unwritable" / "subdir"
        unwritable_subdir.mkdir(parents=True)

        photo_moved = unwritable_subdir / "photo.jpg"
        photo_moved.touch()
        # JSON stayed in original location
        sidecar = subdir / "photo.jpg.json"
        sidecar.touch()

        assert reader.find_json(photo_moved, scan_root=scan_root) == sidecar

    def test_returns_none_when_no_json_in_any_location(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        scan_root = tmp_path
        unwritable = tmp_path / "_unwritable"
        unwritable.mkdir()
        photo = unwritable / "photo.jpg"
        photo.touch()
        assert reader.find_json(photo, scan_root=scan_root) is None

    def test_scan_root_none_does_not_search_outside(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        # Without scan_root, the outside-dir JSON must not be found.
        unwritable = tmp_path / "_unwritable"
        unwritable.mkdir()
        photo = unwritable / "photo.jpg"
        photo.touch()
        # JSON only in the parent, not in _unwritable/
        sidecar = tmp_path / "photo.jpg.json"
        sidecar.touch()
        assert reader.find_json(photo) is None

    # ── Prefix-match fallback ─────────────────────────────────────────────────

    def test_finds_truncated_supplemental_by_prefix(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        # Windows MAX_PATH extraction can truncate "supplemental-metadata.json"
        # to something like "supplemen.json".  The prefix match must catch it.
        photo = tmp_path / "v12044gd0000cjv2633c77u6uhohmah0.mp4"
        photo.touch()
        sidecar = tmp_path / "v12044gd0000cjv2633c77u6uhohmah0.mp4.supplemen.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_prefix_match_on_stem(self, tmp_path: Path, reader: GoogleJsonReader) -> None:
        # Sidecar named <stem>.<anything>.json — still found by prefix on stem.
        photo = tmp_path / "photo.jpg"
        photo.touch()
        sidecar = tmp_path / "photo.truncated-suffix.json"
        sidecar.touch()
        assert reader.find_json(photo) == sidecar

    def test_prefix_match_does_not_match_unrelated_files(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        photo = tmp_path / "photo.jpg"
        photo.touch()
        # "photo2.jpg.json" starts with "photo" but NOT with "photo." or "photo.jpg."
        unrelated = tmp_path / "photo2.jpg.json"
        unrelated.touch()
        assert reader.find_json(photo) is None

    # ── Title-match fallback ──────────────────────────────────────────────────

    def test_finds_json_by_title_field(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        # JSON filename bears no resemblance to the photo — matched purely by title.
        photo = tmp_path / "v12044gd0000cjv2633c77u6uhohmah0.mp4"
        photo.touch()
        sidecar = tmp_path / "completely_different_name.json"
        sidecar.write_text(
            '{"title": "v12044gd0000cjv2633c77u6uhohmah0.mp4",'
            ' "photoTakenTime": {"timestamp": "1694827794"}}',
            encoding="utf-8",
        )
        assert reader.find_json(photo) == sidecar

    def test_title_match_by_stem(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        # JSON title is just the stem without extension — still matched.
        photo = tmp_path / "photo.jpg"
        photo.touch()
        sidecar = tmp_path / "other.json"
        sidecar.write_text('{"title": "photo"}', encoding="utf-8")
        assert reader.find_json(photo) == sidecar

    def test_title_match_skips_malformed_json(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        photo = tmp_path / "photo.jpg"
        photo.touch()
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {{{", encoding="utf-8")
        # Should not raise — just returns None
        assert reader.find_json(photo) is None

    def test_exact_match_preferred_over_title_match(
        self, tmp_path: Path, reader: GoogleJsonReader
    ) -> None:
        photo = tmp_path / "photo.jpg"
        photo.touch()
        exact = tmp_path / "photo.jpg.json"
        exact.touch()
        title_match = tmp_path / "other.json"
        title_match.write_text('{"title": "photo.jpg"}', encoding="utf-8")
        assert reader.find_json(photo) == exact


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
