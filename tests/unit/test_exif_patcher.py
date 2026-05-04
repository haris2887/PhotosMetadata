from __future__ import annotations

from pathlib import Path

import pytest

from core.exif_writer import _patch_other_image_start


def _make_ifd_entry(tag: int, type_: int, count: int, value: int, le: bool) -> bytes:
    bo = "little" if le else "big"
    return (
        tag.to_bytes(2, bo)
        + type_.to_bytes(2, bo)
        + count.to_bytes(4, bo)
        + value.to_bytes(4, bo)
    )


def _build_jpeg_with_corrupt_other_image(tmp_path: Path, little_endian: bool = True) -> Path:
    """
    Build a minimal JPEG with an EXIF APP1 containing:
      - IFD0 with tag 0x8769 pointing to ExifIFD
      - ExifIFD with tag 0x0201 (OtherImageStart) at garbage offset 0xDEADBEEF
    """
    bo = "little" if little_endian else "big"
    bo_mark = b"II" if little_endian else b"MM"
    magic = b"\x2a\x00" if little_endian else b"\x00\x2a"

    def u16(v: int) -> bytes: return v.to_bytes(2, bo)
    def u32(v: int) -> bytes: return v.to_bytes(4, bo)

    # ExifIFD: one entry — OtherImageStart with garbage offset
    exif_ifd = u16(1) + _make_ifd_entry(0x0201, 4, 1, 0xDEADBEEF, little_endian) + u32(0)

    # TIFF layout from the start of the TIFF header:
    #   [0x00] 8-byte TIFF header
    #   [0x08] IFD0: count(2) + 1 entry(12) + next(4) = 18 bytes
    #   [0x1A] ExifIFD
    ifd0_rel = 8
    exif_ifd_rel = ifd0_rel + 2 + 12 + 4   # 26 = 0x1A

    ifd0 = u16(1) + _make_ifd_entry(0x8769, 4, 1, exif_ifd_rel, little_endian) + u32(0)
    tiff_header = bo_mark + magic + u32(ifd0_rel)
    tiff = tiff_header + ifd0 + exif_ifd

    exif_payload = b"Exif\x00\x00" + tiff
    app1_length = 2 + len(exif_payload)
    app1 = b"\xFF\xE1" + app1_length.to_bytes(2, "big") + exif_payload

    path = tmp_path / "test_corrupt.jpg"
    path.write_bytes(b"\xFF\xD8" + app1 + b"\xFF\xD9")
    return path


class TestPatchOtherImageStart:
    def test_patches_corrupt_offset_little_endian(self, tmp_path: Path) -> None:
        path = _build_jpeg_with_corrupt_other_image(tmp_path, little_endian=True)
        assert _patch_other_image_start(path) is True

    def test_patches_corrupt_offset_big_endian(self, tmp_path: Path) -> None:
        path = _build_jpeg_with_corrupt_other_image(tmp_path, little_endian=False)
        assert _patch_other_image_start(path) is True

    def test_corrupt_offset_zeroed_after_patch(self, tmp_path: Path) -> None:
        path = _build_jpeg_with_corrupt_other_image(tmp_path, little_endian=True)
        _patch_other_image_start(path)
        data = path.read_bytes()
        # The garbage offset 0xDEADBEEF should no longer appear
        assert b"\xDE\xAD\xBE\xEF" not in data

    def test_count_field_preserved_after_patch(self, tmp_path: Path) -> None:
        # count must remain 1 — zeroing it causes Perl arithmetic errors in ExifTool write
        path = _build_jpeg_with_corrupt_other_image(tmp_path, little_endian=True)
        data_before = bytearray(path.read_bytes())
        _patch_other_image_start(path)
        data_after = path.read_bytes()
        # Find the IFD entry for 0x0201 and verify count (bytes entry+4..entry+8) is unchanged
        # The count bytes in the test fixture are b"\x01\x00\x00\x00" (count=1, little-endian)
        assert b"\x01\x00\x00\x00" + b"\x00\x00\x00\x00" in data_after  # count=1, value=0

    def test_idempotent_second_call(self, tmp_path: Path) -> None:
        path = _build_jpeg_with_corrupt_other_image(tmp_path, little_endian=True)
        assert _patch_other_image_start(path) is True
        assert _patch_other_image_start(path) is False  # value already 0x00000000

    def test_returns_false_for_non_jpeg(self, tmp_path: Path) -> None:
        path = tmp_path / "notajpeg.jpg"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert _patch_other_image_start(path) is False

    def test_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "ghost.jpg"
        assert _patch_other_image_start(path) is False

    def test_returns_false_when_tag_absent(self, tmp_path: Path) -> None:
        # ExifIFD with zero entries — no 0x0201 tag present
        bo = "little"
        def u16(v: int) -> bytes: return v.to_bytes(2, bo)
        def u32(v: int) -> bytes: return v.to_bytes(4, bo)

        exif_ifd = u16(0) + u32(0)  # 0 entries + next=0
        ifd0_rel = 8
        exif_ifd_rel = ifd0_rel + 2 + 12 + 4
        ifd0 = u16(1) + _make_ifd_entry(0x8769, 4, 1, exif_ifd_rel, True) + u32(0)
        tiff = b"II\x2a\x00" + u32(ifd0_rel) + ifd0 + exif_ifd
        exif_payload = b"Exif\x00\x00" + tiff
        app1_length = 2 + len(exif_payload)
        jpeg = b"\xFF\xD8\xFF\xE1" + app1_length.to_bytes(2, "big") + exif_payload + b"\xFF\xD9"
        path = tmp_path / "no_other_image.jpg"
        path.write_bytes(jpeg)
        assert _patch_other_image_start(path) is False
