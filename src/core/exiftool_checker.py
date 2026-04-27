from __future__ import annotations

import subprocess


def check_exiftool(exiftool_path: str = "exiftool") -> tuple[bool, str]:
    """
    Run `exiftool -ver` to verify the binary is available.
    Returns (available, version_string_or_error_message).
    """
    try:
        result = subprocess.run(
            [exiftool_path, "-ver"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, f"ExifTool not found at: {exiftool_path!r}"
    except subprocess.TimeoutExpired:
        return False, "ExifTool timed out"
    except OSError as exc:
        return False, str(exc)
