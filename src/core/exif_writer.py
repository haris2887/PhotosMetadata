from __future__ import annotations

import logging
import subprocess
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.exceptions import ExifToolNotFoundError, ExifToolProcessError
from models.photo_file import WriteResult
from utils.date_utils import datetime_to_exif_str

logger = logging.getLogger(__name__)

# Map of magic-byte prefix → correct file extension (lowercase, with dot).
# Used to detect files whose extension doesn't match their actual content.
_MAGIC_TO_EXT: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff",           ".jpg"),   # JPEG
    (b"\x89PNG\r\n\x1a\n",      ".png"),   # PNG
    (b"GIF87a",                  ".gif"),
    (b"GIF89a",                  ".gif"),
    (b"\x49\x49\x2a\x00",       ".tif"),   # TIFF little-endian
    (b"\x4d\x4d\x00\x2a",       ".tif"),   # TIFF big-endian
    (b"\x1a\x45\xdf\xa3",       ".mkv"),   # MKV / WebM (EBML)
    (b"RIFF",                    ".avi"),   # AVI
]

# ftyp brand codes for ISO Base Media files (MP4, M4V, HEIC, MOV …)
_HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}
_MOV_BRANDS  = {b"qt  "}
_M4V_BRANDS  = {b"M4V ", b"M4VH", b"M4VP"}


def _detect_actual_extension(path: Path) -> str | None:
    """
    Read the first 16 bytes of a file and return the extension it *should* have,
    or None if the format is unrecognised or already matches.
    """
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return None

    for magic, ext in _MAGIC_TO_EXT:
        if header.startswith(magic):
            return ext

    # ISO Base Media File Format: [4-byte size][4-byte 'ftyp'][4-byte brand]
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in _HEIC_BRANDS:
            return ".heic"
        if brand in _MOV_BRANDS:
            return ".mov"
        if brand in _M4V_BRANDS:
            return ".m4v"
        return ".mp4"

    return None


_KNOWN_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".m4v",
    ".mkv", ".avi", ".tif", ".tiff", ".gif",
)


def _fix_extension(path: Path) -> Path:
    """
    If the file's magic bytes indicate a different format than its extension,
    rename it in-place and return the new path.  Returns the original path
    unchanged if no rename is needed or possible.

    Also handles stale scan-result paths: if the file no longer exists at the
    recorded path (because it was already renamed in a previous run), search
    for a same-stem file with a different extension and return that instead.
    """
    if not path.exists():
        # File may have been renamed by a prior _fix_extension call.
        for alt_ext in _KNOWN_EXTENSIONS:
            candidate = path.with_suffix(alt_ext)
            if candidate.exists() and candidate.suffix.lower() != path.suffix.lower():
                logger.info(
                    "File %s not found; found previously renamed %s",
                    path.name, candidate.name,
                )
                return candidate
        # Nothing found — return as-is; ExifTool will report "File not found"
        logger.warning("File not found and no renamed version located: %s", path)
        return path

    actual_ext = _detect_actual_extension(path)
    if actual_ext is None or path.suffix.lower() == actual_ext:
        return path  # already correct

    new_path = path.with_suffix(actual_ext)
    if new_path.exists():
        # Avoid clobbering a different file that already has the right name
        logger.warning(
            "Cannot rename %s → %s: target already exists", path.name, new_path.name
        )
        return path

    try:
        path.rename(new_path)
        logger.info("Renamed %s → %s (extension mismatch corrected)", path.name, new_path.name)
        return new_path
    except OSError as exc:
        logger.warning("Could not rename %s: %s", path.name, exc)
        return path


# ---------------------------------------------------------------------------
# Binary EXIF patcher for corrupt OtherImageStart
# ---------------------------------------------------------------------------

def _jpeg_exif_tiff_start(data: bytes) -> int | None:
    """Return the offset of the TIFF header inside a JPEG's EXIF APP1, or None."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 3 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xDA or marker == 0xD9:   # SOS / EOI
            return None
        seg_len = (data[i + 2] << 8) | data[i + 3]
        if marker == 0xE1:
            payload_start = i + 4
            if (payload_start + 6 <= len(data)
                    and data[payload_start:payload_start + 6] == b"Exif\x00\x00"):
                return payload_start + 6
        i += 2 + seg_len
    return None


def _u16(data: bytes | bytearray, off: int, le: bool) -> int:
    return int.from_bytes(data[off:off + 2], "little" if le else "big")


def _u32(data: bytes | bytearray, off: int, le: bool) -> int:
    return int.from_bytes(data[off:off + 4], "little" if le else "big")


def _ifd_tag_value_offset(
    data: bytes | bytearray,
    tiff_start: int,
    ifd_rel_offset: int,
    target_tag: int,
    le: bool,
) -> int | None:
    """
    Walk one IFD and return the absolute offset in `data` of the 12-byte
    IFD entry for `target_tag`, or None if not found.
    """
    abs_ifd = tiff_start + ifd_rel_offset
    if abs_ifd + 2 > len(data):
        return None
    count = _u16(data, abs_ifd, le)
    for i in range(min(count, 1000)):
        entry = abs_ifd + 2 + i * 12
        if entry + 12 > len(data):
            break
        if _u16(data, entry, le) == target_tag:
            return entry
    return None


def _patch_other_image_start(path: Path) -> bool:
    """
    Binary-patch a JPEG to neutralise a corrupt OtherImageStart (tag 0x0201)
    and OtherImageLength (tag 0x0202) in the ExifIFD.

    Some 2016-era Android JPEGs embed a secondary image in the ExifIFD using
    the same tag numbers as IFD1 thumbnails.  When the offset is garbage
    ExifTool aborts with "Error reading OtherImageStart data in ExifIFD".

    We zero only the 4-byte offset value of those IFD entries, leaving the
    count field intact (count=0 triggers Perl arithmetic errors in ExifTool's
    write phase).  ExifTool then reads OtherImageStart=0 as a pointer to the
    TIFF header (harmless garbage); the -m flag suppresses the resulting minor
    warning so the write succeeds.  Only 4 bytes per tag are changed; the
    JPEG pixel stream is completely untouched.

    Returns True if at least one tag was patched.
    """
    try:
        data = bytearray(path.read_bytes())
    except OSError:
        return False

    tiff_start = _jpeg_exif_tiff_start(bytes(data))
    if tiff_start is None or tiff_start + 8 > len(data):
        return False

    hdr = data[tiff_start:tiff_start + 2]
    if hdr == b"II":
        le = True
    elif hdr == b"MM":
        le = False
    else:
        return False

    ifd0_rel = _u32(data, tiff_start + 4, le)

    # Tag 0x8769 in IFD0 → ExifIFD relative offset
    exif_ptr_entry = _ifd_tag_value_offset(data, tiff_start, ifd0_rel, 0x8769, le)
    if exif_ptr_entry is None:
        return False
    exif_ifd_rel = _u32(data, exif_ptr_entry + 8, le)

    patched = False
    for tag in (0x0201, 0x0202):   # OtherImageStart, OtherImageLength
        entry = _ifd_tag_value_offset(data, tiff_start, exif_ifd_rel, tag, le)
        if entry is None:
            continue
        # Zero only the 4-byte value/offset field (entry+8..entry+12).
        # Do NOT touch the count field — count=0 causes Perl arithmetic errors
        # in ExifTool's write phase ("Argument isn't numeric in addition").
        # ExifTool reads offset=0 as OtherImageStart pointing to TIFF start
        # (harmless garbage); the -m flag suppresses the resulting minor error
        # so the write succeeds.
        if data[entry + 8:entry + 12] == b"\x00\x00\x00\x00":
            continue  # already zeroed
        old_val = _u32(data, entry + 8, le)
        data[entry + 8:entry + 12] = b"\x00\x00\x00\x00"
        logger.info(
            "Patched corrupt EXIF tag 0x%04X (was 0x%08X) in ExifIFD of %s",
            tag, old_val, path.name,
        )
        patched = True

    if not patched:
        return False

    try:
        path.write_bytes(data)
        return True
    except OSError as exc:
        logger.warning("Could not write patched EXIF to %s: %s", path.name, exc)
        return False


class ExifWriter:
    def __init__(
        self,
        exiftool_path: str = "exiftool",
        create_backup: bool = True,
    ) -> None:
        self._exiftool_path = exiftool_path
        self._create_backup = create_backup

    def write_date(self, path: Path, date: datetime) -> WriteResult:
        """Write a single file's date. Returns WriteResult."""
        results = self.write_batch([(path, date)])
        return results[0]

    def write_batch(
        self,
        tasks: list[tuple[Path, datetime]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[WriteResult]:
        """
        Write dates to multiple files using a single ExifTool invocation via argfile.

        Before writing, each file's magic bytes are checked.  If the extension
        doesn't match the actual format (e.g. a JPEG saved as .PNG by Google
        Photos), the file is renamed to the correct extension so ExifTool can
        write to it successfully.

        ExifTool creates <filename>_original backups automatically unless
        create_backup=False, in which case -overwrite_original is used.
        The -m flag is always added to suppress minor EXIF structural errors.

        Files that fail due to a corrupt OtherImageStart IFD pointer (a common
        Android camera bug in 2016-era photos) are binary-patched to null out
        the corrupt offset, then retried with ExifTool.
        """
        if not tasks:
            return []

        # Pre-flight: fix any extension mismatches before building the argfile.
        fixed_tasks: list[tuple[Path, datetime]] = []
        for path, date in tasks:
            fixed_tasks.append((_fix_extension(path), date))

        # First pass — normal write
        output_lines, error_lines = self._run_exiftool_batch(fixed_tasks, extra_flags=[])

        results: list[WriteResult | None] = [None] * len(fixed_tasks)
        retry_indices: list[int] = []

        for i, (path, _date) in enumerate(fixed_tasks):
            backup = Path(str(path) + "_original")
            success = self._parse_success(output_lines, i)

            if not success and any(
                "OtherImageStart" in line and path.name in line
                for line in error_lines
            ):
                # Binary-patch the corrupt ExifIFD pointer, then retry
                retry_indices.append(i)
            else:
                results[i] = WriteResult(
                    path=path,
                    success=success,
                    backup_path=backup if backup.exists() else None,
                    error=None if success else f"ExifTool reported 0 files updated for {path.name}",
                )

            if progress_callback:
                progress_callback(i + 1, len(fixed_tasks))

        # Second pass — binary-patch OtherImageStart then retry with ExifTool
        if retry_indices:
            patch_tasks: list[tuple[Path, datetime]] = []
            skipped: list[int] = []
            for original_i in retry_indices:
                path, date = fixed_tasks[original_i]
                if _patch_other_image_start(path):
                    patch_tasks.append((path, date))
                else:
                    skipped.append(original_i)
                    results[original_i] = WriteResult(
                        path=path,
                        success=False,
                        backup_path=None,
                        error=f"OtherImageStart corrupt and could not be patched: {path.name}",
                    )

            if patch_tasks:
                logger.info(
                    "Retrying %d file(s) after binary-patching corrupt OtherImageStart",
                    len(patch_tasks),
                )
                retry_output, retry_errors = self._run_exiftool_batch(patch_tasks, extra_flags=[])
                if retry_errors:
                    logger.warning("ExifTool retry stderr: %s", retry_errors)

                # Map retry results back to original indices
                patch_index_map = [i for i in retry_indices if i not in skipped]
                for j, original_i in enumerate(patch_index_map):
                    path, _date = fixed_tasks[original_i]
                    backup = Path(str(path) + "_original")
                    success = self._parse_success(retry_output, j)
                    results[original_i] = WriteResult(
                        path=path,
                        success=success,
                        backup_path=backup if backup.exists() else None,
                        error=None if success else f"ExifTool retry failed for {path.name}",
                    )

        return [r for r in results if r is not None]

    def _run_exiftool_batch(
        self,
        tasks: list[tuple[Path, datetime]],
        extra_flags: list[str],
    ) -> tuple[list[str], list[str]]:
        """Build an argfile and run ExifTool. Returns (stdout_lines, stderr_lines)."""
        argfile_lines: list[str] = []
        for path, date in tasks:
            date_str = datetime_to_exif_str(date)
            block: list[str] = ["-m"]   # ignore minor EXIF structural errors
            if not self._create_backup:
                block.append("-overwrite_original")
            block += extra_flags
            block += [
                f"-DateTimeOriginal={date_str}",
                f"-CreateDate={date_str}",
                str(path),
                "-execute",
            ]
            argfile_lines += block

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(argfile_lines) + "\n")
            argfile_path = f.name

        try:
            proc = subprocess.run(
                [self._exiftool_path, "-@", argfile_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise ExifToolNotFoundError(str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise ExifToolProcessError("ExifTool batch write timed out") from exc
        finally:
            Path(argfile_path).unlink(missing_ok=True)

        output_lines = proc.stdout.splitlines()
        error_lines = proc.stderr.splitlines() if proc.stderr else []
        logger.debug("ExifTool write output: %s", output_lines)
        if error_lines:
            logger.warning("ExifTool write stderr: %s", error_lines)

        return output_lines, error_lines

    def _parse_success(self, output_lines: list[str], index: int) -> bool:
        """Find the N-th '1 image files updated' line in ExifTool output."""
        updated_lines = [
            l for l in output_lines
            if "image files updated" in l or "image files unchanged" in l
        ]
        if index < len(updated_lines):
            return updated_lines[index].strip().startswith("1 ")
        return True
